"""ULID-based ID generation with typed entity prefixes.

Supported prefixes:
- ds: Dataset
- dv: DatasetVersion
- ses: AnalysisSession
- ev: Evidence
- fd: Finding
- ch: Chart
- rp: Report
- at: AttestationRecord
- as: Assumption
- wk: Workspace
- job: Background Job
"""

import os
import re
import secrets
import time
from typing import Literal

CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ULID_RE = re.compile(r"^[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{26}$", re.IGNORECASE)

IdPrefix = Literal["ds", "dv", "ses", "ev", "fd", "ch", "rp", "at", "as", "wk", "job"]

KNOWN_PREFIXES: set[str] = {
    "ds",
    "dv",
    "ses",
    "ev",
    "fd",
    "ch",
    "rp",
    "at",
    "as",
    "wk",
    "job",
}


def generate_ulid(timestamp_ms: int | None = None) -> str:
    """Generate a standard 26-character Crockford Base32 ULID."""
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    # 48-bit timestamp + 80-bit random payload
    rand_bytes = secrets.token_bytes(10)
    val = (timestamp_ms << 80) | int.from_bytes(rand_bytes, "big")

    chars = []
    for _ in range(26):
        chars.append(CROCKFORD_BASE32[val & 31])
        val >>= 5
    return "".join(reversed(chars))


def generate_id(prefix: str, lowercase: bool = True) -> str:
    """Generate a prefixed ULID string, e.g. 'ds_01h7x...' or 'ev_01h7x...'."""
    clean_prefix = prefix.rstrip("_")
    ulid_str = generate_ulid()
    if lowercase:
        return f"{clean_prefix}_{ulid_str.lower()}"
    return f"{clean_prefix}_{ulid_str}"


def new_id(prefix: str, lowercase: bool = True) -> str:
    """Alias for generate_id."""
    return generate_id(prefix, lowercase=lowercase)


def is_valid_id(id_str: str, expected_prefix: str | None = None) -> bool:
    """Check if an ID string is well-formed with a prefix and 26-char ULID."""
    if not isinstance(id_str, str) or "_" not in id_str:
        return False
    parts = id_str.split("_", 1)
    if len(parts) != 2:
        return False
    prefix, ulid_part = parts
    if expected_prefix is not None and prefix != expected_prefix.rstrip("_"):
        return False
    if not ULID_RE.match(ulid_part):
        return False
    return True
