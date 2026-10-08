"""Pydantic domain models for data sufficiency checking and gap diagnosis."""

from typing import Literal
from pydantic import BaseModel, Field


class Requirement(BaseModel):
    """Semantic data requirement necessary to answer an analytical question."""

    role: str  # e.g. "date", "measure:outflow_usd", "identifier:tx_signature"
    min_coverage: str = "0.90"  # Stored as decimal string to avoid float serialization issues
    note: str | None = None


class RequirementCheck(BaseModel):
    """Diagnostic check evaluation of a specific data requirement."""

    requirement: Requirement
    status: Literal["ok", "missing", "low_coverage", "grain_mismatch", "too_few_rows", "too_short_span"]
    detail: str


class SufficiencyResult(BaseModel):
    """Overall data sufficiency verdict and structured actionable gap report."""

    verdict: Literal["ANSWERABLE", "ANSWERABLE_WITH_CAVEATS", "PARTIAL", "INSUFFICIENT_DATA"]
    checks: list[RequirementCheck] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    answerable_now: list[str] = Field(default_factory=list)  # Sub-questions answerable immediately
    missing: list[str] = Field(default_factory=list)  # Elements to prompt the user to upload/provide
