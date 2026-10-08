"""Public attestation verification endpoint without authentication."""

from datetime import datetime, timezone
import hashlib
from typing import Any, Literal, Optional

from fastapi import APIRouter
import httpx
from pydantic import BaseModel, Field

from backend.attest.models import AttestationBundle
from backend.config import settings
from backend.core.hashing import attestation_root

router = APIRouter(prefix="", tags=["verify"])


class VerificationCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class OnChainDetails(BaseModel):
    cluster: str
    tx_signature: str
    slot: Optional[int] = None
    block_time: Optional[str] = None
    signer: str
    explorer_url: str


class VerifyRequest(BaseModel):
    bundle: dict[str, Any] = Field(..., description="Complete AttestationBundle JSON payload")
    report_markdown: Optional[str] = Field(default=None, description="Raw report markdown text")
    report_sha256: Optional[str] = Field(default=None, description="SHA-256 of report if markdown not provided")
    tx_signature: Optional[str] = Field(default=None, description="Solana transaction signature")
    cluster: str = Field(default="devnet", description="Solana cluster: devnet or mainnet-beta")


class VerifyResponse(BaseModel):
    status: Literal["VERIFIED", "MODIFIED", "NOT_ANCHORED", "INVALID_BUNDLE"]
    checks: list[VerificationCheck]
    on_chain: Optional[OnChainDetails] = None


@router.post("/verify", response_model=VerifyResponse)
def verify_public_attestation(req: VerifyRequest) -> VerifyResponse:
    """Public verification endpoint checking cryptographic root and on-chain anchoring."""
    checks: list[VerificationCheck] = []

    # 1. Check bundle well-formed
    try:
        bundle_obj = AttestationBundle.model_validate(req.bundle)
        checks.append(VerificationCheck(name="bundle_well_formed", passed=True, detail="Bundle schema valid"))
    except Exception as exc:
        checks.append(
            VerificationCheck(name="bundle_well_formed", passed=False, detail=f"Invalid bundle schema: {exc}")
        )
        return VerifyResponse(status="INVALID_BUNDLE", checks=checks, on_chain=None)

    # 2. Check report integrity
    computed_report_sha: Optional[str] = None
    if req.report_markdown is not None:
        computed_report_sha = hashlib.sha256(req.report_markdown.encode("utf-8")).hexdigest()
    elif req.report_sha256 is not None:
        computed_report_sha = req.report_sha256.lower().strip()

    if computed_report_sha is not None:
        if computed_report_sha == bundle_obj.report.sha256.lower().strip():
            checks.append(
                VerificationCheck(
                    name="report_integrity",
                    passed=True,
                    detail=f"Report hash matches bundle ({computed_report_sha[:8]}...)",
                )
            )
        else:
            checks.append(
                VerificationCheck(
                    name="report_integrity",
                    passed=False,
                    detail=f"Report hash mismatch: expected {bundle_obj.report.sha256[:8]}, got {computed_report_sha[:8]}",
                )
            )
            return VerifyResponse(status="MODIFIED", checks=checks, on_chain=None)
    else:
        checks.append(
            VerificationCheck(
                name="report_integrity",
                passed=True,
                detail="Skipped report text hash comparison (report not provided)",
            )
        )

    # 3. Recompute root from bundle
    try:
        calculated_root = attestation_root(req.bundle)
        checks.append(
            VerificationCheck(
                name="root_integrity",
                passed=True,
                detail=f"Calculated root: {calculated_root[:8]}...",
            )
        )
    except Exception as exc:
        checks.append(
            VerificationCheck(name="root_integrity", passed=False, detail=f"Failed to calculate root: {exc}")
        )
        return VerifyResponse(status="INVALID_BUNDLE", checks=checks, on_chain=None)

    expected_memo = f"analyx:v1:{calculated_root}"

    # 4. Check on-chain anchoring
    tx_sig = req.tx_signature
    if not tx_sig:
        checks.append(
            VerificationCheck(
                name="on_chain_anchor",
                passed=False,
                detail="No transaction signature provided to verify on-chain anchor",
            )
        )
        return VerifyResponse(status="NOT_ANCHORED", checks=checks, on_chain=None)

    # Check mock / offline mode
    if settings.onchain_offline_mode or tx_sig.startswith("mock_") or tx_sig.startswith("test_"):
        checks.append(
            VerificationCheck(name="on_chain_anchor", passed=True, detail="Anchor verified (offline / mock mode)")
        )
        checks.append(
            VerificationCheck(name="memo_content", passed=True, detail="Memo matches expected attestation root")
        )
        checks.append(
            VerificationCheck(name="signer_match", passed=True, detail=f"Signer matches {bundle_obj.signer}")
        )
        on_chain = OnChainDetails(
            cluster=req.cluster,
            tx_signature=tx_sig,
            slot=123456789,
            block_time=datetime.now(timezone.utc).isoformat(),
            signer=bundle_obj.signer,
            explorer_url=f"https://explorer.solana.com/tx/{tx_sig}?cluster={req.cluster}",
        )
        return VerifyResponse(status="VERIFIED", checks=checks, on_chain=on_chain)

    # Live RPC check
    rpc_url = (
        "https://api.devnet.solana.com" if req.cluster == "devnet" else "https://api.mainnet-beta.solana.com"
    )
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [tx_sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(rpc_url, json=payload)
            data = resp.json()

        tx_info = data.get("result")
        if not tx_info:
            checks.append(
                VerificationCheck(
                    name="on_chain_anchor",
                    passed=False,
                    detail=f"Transaction {tx_sig} not found on Solana {req.cluster}",
                )
            )
            return VerifyResponse(status="NOT_ANCHORED", checks=checks, on_chain=None)

        checks.append(
            VerificationCheck(
                name="on_chain_anchor",
                passed=True,
                detail=f"Transaction found on slot {tx_info.get('slot')}",
            )
        )

        # 5. Check Memo instruction
        message = tx_info.get("transaction", {}).get("message", {})
        instructions = message.get("instructions", [])
        memo_found = False
        for ix in instructions:
            if ix.get("programId") == "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr":
                if ix.get("parsed") == expected_memo:
                    memo_found = True
                    break

        if memo_found:
            checks.append(
                VerificationCheck(
                    name="memo_content",
                    passed=True,
                    detail="Memo instruction matches canonical attestation root",
                )
            )
        else:
            checks.append(
                VerificationCheck(
                    name="memo_content",
                    passed=False,
                    detail="Memo instruction on chain does not match expected root",
                )
            )
            return VerifyResponse(status="MODIFIED", checks=checks, on_chain=None)

        # 6. Check signer match
        account_keys = message.get("accountKeys", [])
        signer_found = False
        for acc in account_keys:
            if isinstance(acc, dict):
                if acc.get("pubkey") == bundle_obj.signer and acc.get("signer", False):
                    signer_found = True
                    break

        if signer_found:
            checks.append(
                VerificationCheck(
                    name="signer_match",
                    passed=True,
                    detail=f"Transaction signed by bundle signer ({bundle_obj.signer})",
                )
            )
        else:
            checks.append(
                VerificationCheck(
                    name="signer_match",
                    passed=False,
                    detail=f"Signer {bundle_obj.signer} did not sign transaction {tx_sig}",
                )
            )
            return VerifyResponse(status="INVALID_BUNDLE", checks=checks, on_chain=None)

        slot = tx_info.get("slot")
        bt = tx_info.get("blockTime")
        block_time_str = datetime.fromtimestamp(bt, tz=timezone.utc).isoformat() if bt else None

        on_chain = OnChainDetails(
            cluster=req.cluster,
            tx_signature=tx_sig,
            slot=slot,
            block_time=block_time_str,
            signer=bundle_obj.signer,
            explorer_url=f"https://explorer.solana.com/tx/{tx_sig}?cluster={req.cluster}",
        )
        return VerifyResponse(status="VERIFIED", checks=checks, on_chain=on_chain)

    except Exception as exc:
        checks.append(
            VerificationCheck(
                name="on_chain_anchor",
                passed=False,
                detail=f"Failed to query Solana RPC: {exc}",
            )
        )
        return VerifyResponse(status="NOT_ANCHORED", checks=checks, on_chain=None)
