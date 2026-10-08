"""Core package — shared utilities."""

from backend.core.errors import (
    AnalyxError,
    AttestationError,
    AuthError,
    BudgetExceededError,
    EngineError,
    FloatNotAllowedError,
    IngestError,
    NotFoundError,
    SufficiencyError,
    ValidationError,
)
from backend.core.hashing import (
    attestation_root,
    canonical_table_hash,
    hash_obj,
    jcs,
    sha256_hex,
)
from backend.core.ids import generate_id, is_valid_id, new_id
from backend.core.time_anchor import (
    TimeWindow,
    get_last_complete_month,
    get_prior_period,
    is_month_complete,
    resolve_anchor,
    resolve_window,
    to_utc_datetime,
)

__all__ = [
    "generate_id",
    "new_id",
    "is_valid_id",
    "AnalyxError",
    "ValidationError",
    "FloatNotAllowedError",
    "IngestError",
    "EngineError",
    "SufficiencyError",
    "AttestationError",
    "AuthError",
    "NotFoundError",
    "BudgetExceededError",
    "sha256_hex",
    "jcs",
    "hash_obj",
    "canonical_table_hash",
    "attestation_root",
    "TimeWindow",
    "resolve_anchor",
    "resolve_window",
    "get_last_complete_month",
    "get_prior_period",
    "is_month_complete",
    "to_utc_datetime",
]
