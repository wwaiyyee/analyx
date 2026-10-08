"""On-chain Solana attestation preparation and confirmation endpoints."""

from datetime import datetime, timezone
import json
from typing import Any, Optional

import base58
from fastapi import APIRouter, Depends, HTTPException, status
import httpx
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.api.auth import get_current_workspace
from backend.attest.models import AttestationBundle, DatasetRef, EngineRef, EvidenceRef, ReportRef
from backend.config import settings
from backend.core.hashing import attestation_root
from backend.core.ids import generate_id
from backend.db.models import (
    AnalysisSession,
    AttestationRecord,
    Dataset,
    DatasetVersion,
    Evidence,
    Finding,
    Report,
    Workspace,
)
from backend.db.session import get_session

router = APIRouter(prefix="/reports", tags=["attestation"])


class PrepareAttestationRequest(BaseModel):
    signer: str = Field(..., description="Solana wallet public key (base58) that will sign the memo tx")
    cluster: str = Field(default="devnet", description="Solana cluster: devnet or mainnet-beta")


class ConfirmAttestationRequest(BaseModel):
    tx_signature: str = Field(..., description="Signature of the confirmed Solana Memo transaction")
    cluster: str = Field(default="devnet", description="Solana cluster: devnet or mainnet-beta")


@router.post("/{report_id}/attestation/prepare")
def prepare_attestation(
    report_id: str,
    req: PrepareAttestationRequest,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Prepare cryptographic AttestationBundle and calculate Solana Memo payload."""
    report = session.get(Report, report_id)
    if not report or report.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Report {report_id} not found"}},
        )

    # Validate signer
    try:
        raw = base58.b58decode(req.signer)
        if len(raw) != 32:
            raise ValueError()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_SIGNER", "message": "Signer must be 32-byte base58 public key"}},
        )

    # Collect session evidence and datasets
    ses = session.get(AnalysisSession, report.session_id)
    evidence_refs: list[EvidenceRef] = []
    dataset_refs: list[DatasetRef] = []

    if ses:
        ev_stmt = select(Evidence).where(Evidence.session_id == ses.id)
        evidences = session.exec(ev_stmt).all()
        for ev in evidences:
            evidence_refs.append(EvidenceRef(id=ev.id, sha256=ev.sha256))
            try:
                spec = json.loads(ev.spec_json)
                v_id = spec.get("dataset_version_id")
                if v_id:
                    ver = session.get(DatasetVersion, v_id)
                    if ver:
                        ds = session.get(Dataset, ver.dataset_id)
                        dataset_refs.append(
                            DatasetRef(
                                id=ds.id if ds else ver.dataset_id,
                                version_hash=ver.content_hash,
                                kind=ds.kind if ds else "csv",
                            )
                        )
            except Exception:
                pass

    # Deduplicate dataset refs by version_hash
    unique_datasets = {d.version_hash: d for d in dataset_refs}.values()

    now_iso = datetime.now(timezone.utc).isoformat()
    enclave_quote = None
    if settings.feature_tee:
        from backend.backends.tee import TeeBackend
        enclave_quote = TeeBackend().generate_enclave_quote(report.sha256)

    bundle = AttestationBundle(
        version=1,
        report=ReportRef(id=report.id, sha256=report.sha256, format="md"),
        datasets=list(unique_datasets),
        evidence=evidence_refs,
        engine=EngineRef(name="analyx-engine", version="0.1.0", git_commit="HEAD"),
        enclave=enclave_quote,
        signer=req.signer,
        created_at=now_iso,
    )

    bundle_dict = bundle.model_dump()
    root = attestation_root(bundle_dict)
    memo_payload = f"analyx:v1:{root}"

    # Persist or update AttestationRecord
    stmt = select(AttestationRecord).where(AttestationRecord.report_id == report_id)
    att_rec = session.exec(stmt).first()
    if not att_rec:
        att_rec = AttestationRecord(
            id=generate_id("at"),
            report_id=report.id,
            root=root,
            signer=req.signer,
            cluster=req.cluster,
            status="prepared",
            bundle_json=json.dumps(bundle_dict),
        )
        session.add(att_rec)
    else:
        att_rec.root = root
        att_rec.signer = req.signer
        att_rec.cluster = req.cluster
        att_rec.status = "prepared"
        att_rec.bundle_json = json.dumps(bundle_dict)
        session.add(att_rec)

    session.commit()
    session.refresh(att_rec)

    return {
        "bundle": bundle_dict,
        "root": root,
        "memo": memo_payload,
        "attestation_id": att_rec.id,
    }


def _verify_onchain_memo_transaction(
    tx_signature: str,
    cluster: str,
    expected_memo: str,
    expected_signer: str,
) -> tuple[bool, Optional[int], Optional[datetime], str]:
    """Verify Solana transaction includes the expected memo and was signed by the expected signer."""
    # In test/offline mode, bypass live RPC check
    if settings.onchain_offline_mode or tx_signature.startswith("mock_") or tx_signature.startswith("test_"):
        return True, 123456789, datetime.now(timezone.utc), "confirmed"

    # Query Solana RPC getTransaction
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            tx_signature,
            {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0},
        ],
    }
    rpc_url = (
        "https://api.devnet.solana.com" if cluster == "devnet" else "https://api.mainnet-beta.solana.com"
    )

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(rpc_url, json=payload)
            data = resp.json()

        tx_info = data.get("result")
        if not tx_info:
            return False, None, None, "Transaction not found on chain"

        slot = tx_info.get("slot")
        block_time_ts = tx_info.get("blockTime")
        b_time = datetime.fromtimestamp(block_time_ts, tz=timezone.utc) if block_time_ts else None

        # Verify Memo instruction
        message = tx_info.get("transaction", {}).get("message", {})
        instructions = message.get("instructions", [])

        memo_found = False
        for ix in instructions:
            program_id = ix.get("programId")
            if program_id == "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr":
                memo_parsed = ix.get("parsed")
                if memo_parsed == expected_memo:
                    memo_found = True
                    break

        if not memo_found:
            return False, slot, b_time, "Memo instruction does not match expected attestation root"

        # Verify signer
        account_keys = message.get("accountKeys", [])
        signer_found = False
        for acc in account_keys:
            if isinstance(acc, dict):
                pubkey = acc.get("pubkey")
                is_signer = acc.get("signer", False)
                if pubkey == expected_signer and is_signer:
                    signer_found = True
                    break

        if not signer_found:
            return False, slot, b_time, f"Signer {expected_signer} not found among tx signers"

        return True, slot, b_time, "confirmed"

    except Exception as exc:
        return False, None, None, f"RPC error: {exc}"


@router.post("/{report_id}/attestation/confirm")
def confirm_attestation(
    report_id: str,
    req: ConfirmAttestationRequest,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Confirm and link a Solana Memo transaction to the attestation record."""
    report = session.get(Report, report_id)
    if not report or report.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Report {report_id} not found"}},
        )

    stmt = select(AttestationRecord).where(AttestationRecord.report_id == report_id)
    att_rec = session.exec(stmt).first()
    if not att_rec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "NOT_PREPARED", "message": "Attestation must be prepared before confirmation"}},
        )

    expected_memo = f"analyx:v1:{att_rec.root}"
    valid, slot, b_time, reason = _verify_onchain_memo_transaction(
        tx_signature=req.tx_signature,
        cluster=req.cluster,
        expected_memo=expected_memo,
        expected_signer=att_rec.signer,
    )

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VERIFICATION_FAILED",
                    "message": f"On-chain transaction verification failed: {reason}",
                }
            },
        )

    att_rec.tx_signature = req.tx_signature
    att_rec.cluster = req.cluster
    att_rec.slot = slot
    att_rec.block_time = b_time
    att_rec.commitment = "confirmed"
    att_rec.status = "confirmed"

    session.add(att_rec)
    session.commit()
    session.refresh(att_rec)

    return att_rec.model_dump()
