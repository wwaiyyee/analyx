"""Attestation root calculation and Solana Memo formatting per §11.2."""

from typing import Any

from backend.attest.models import AttestationBundle
from backend.core.hashing import attestation_root

MEMO_PREFIX = "analyx:v1:"


def compute_attestation_root(bundle: AttestationBundle | dict[str, Any]) -> str:
    """Compute 32-byte hex root hash over canonical RFC 8785 representation of the bundle."""
    bundle_dict = bundle.model_dump() if isinstance(bundle, AttestationBundle) else bundle
    return attestation_root(bundle_dict)


def format_solana_memo(root: str) -> str:
    """Format Solana Memo program payload: analyx:v1:<root>."""
    return f"{MEMO_PREFIX}{root.lower().strip()}"


def parse_memo_root(memo: str) -> str | None:
    """Extract root hash from a Solana memo payload, or None if malformed."""
    s = memo.strip()
    if s.startswith(MEMO_PREFIX):
        candidate = s[len(MEMO_PREFIX) :].strip()
        if len(candidate) == 64:
            return candidate.lower()
    return None
