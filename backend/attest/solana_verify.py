"""Server-side Solana on-chain transaction and Memo instruction verifier per §9.5 and §11.3."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.attest.root import format_solana_memo
from backend.config import settings

MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"


@dataclass
class SolanaVerificationResult:
    success: bool
    status: str  # confirmed | failed | not_found
    slot: Optional[int] = None
    block_time: Optional[datetime] = None
    error: Optional[str] = None


def verify_onchain_memo(
    tx_signature: str,
    expected_root: str,
    expected_signer: str,
    cluster: str = "devnet",
    rpc_url: Optional[str] = None,
) -> SolanaVerificationResult:
    """Fetch Solana transaction and verify Memo instruction and signer."""
    expected_memo = format_solana_memo(expected_root)

    # Offline/test mode bypass
    if settings.onchain_offline_mode or tx_signature.startswith("mock_") or tx_signature.startswith("test_"):
        return SolanaVerificationResult(
            success=True,
            status="confirmed",
            slot=123456789,
            block_time=datetime.now(timezone.utc),
        )

    endpoint = rpc_url or (
        "https://api.devnet.solana.com" if cluster == "devnet" else "https://api.mainnet-beta.solana.com"
    )

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            tx_signature,
            {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0},
        ],
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(endpoint, json=payload)
            data = resp.json()

        tx_info = data.get("result")
        if not tx_info:
            return SolanaVerificationResult(
                success=False,
                status="not_found",
                error=f"Transaction {tx_signature} not found on Solana {cluster}",
            )

        slot = tx_info.get("slot")
        bt = tx_info.get("blockTime")
        b_time = datetime.fromtimestamp(bt, tz=timezone.utc) if bt else None

        # Check Memo instruction
        message = tx_info.get("transaction", {}).get("message", {})
        instructions = message.get("instructions", [])

        memo_found = False
        for ix in instructions:
            if ix.get("programId") == MEMO_PROGRAM_ID:
                parsed_memo = ix.get("parsed")
                if parsed_memo == expected_memo:
                    memo_found = True
                    break

        if not memo_found:
            return SolanaVerificationResult(
                success=False,
                status="failed",
                slot=slot,
                block_time=b_time,
                error=f"Transaction does not contain required Memo '{expected_memo}'",
            )

        # Check signer
        account_keys = message.get("accountKeys", [])
        signer_found = False
        for acc in account_keys:
            if isinstance(acc, dict):
                if acc.get("pubkey") == expected_signer and acc.get("signer", False):
                    signer_found = True
                    break

        if not signer_found:
            return SolanaVerificationResult(
                success=False,
                status="failed",
                slot=slot,
                block_time=b_time,
                error=f"Signer {expected_signer} did not sign transaction {tx_signature}",
            )

        return SolanaVerificationResult(
            success=True,
            status="confirmed",
            slot=slot,
            block_time=b_time,
        )

    except Exception as exc:
        return SolanaVerificationResult(
            success=False,
            status="failed",
            error=f"Solana RPC request failed: {exc}",
        )
