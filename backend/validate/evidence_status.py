"""Rule-based evidence status evaluation and mathematical invariant validation per §8.8 (4, 5)."""

from decimal import Decimal
from typing import Literal, Sequence

EvidenceStatus = Literal["supported", "partially_supported", "insufficient", "not_applicable"]


def check_segment_sum_invariant(
    segments: Sequence[Decimal | str | int | float],
    total: Decimal | str | int | float,
    tolerance: Decimal = Decimal("0.00"),
) -> bool:
    """Validate invariant: Σ segments == total (exact tolerance for decimal money arithmetic)."""
    seg_sum = sum(Decimal(str(s)) for s in segments)
    tot_val = Decimal(str(total))
    return abs(seg_sum - tot_val) <= tolerance


def check_percentage_invariant(
    part: Decimal | str | int | float,
    total: Decimal | str | int | float,
    percent: Decimal | str | int | float,
    tolerance: Decimal = Decimal("0.05"),
) -> bool:
    """Validate invariant: (part / total) * 100 matches stated percentage within rounding tolerance."""
    tot_dec = Decimal(str(total))
    if tot_dec == 0:
        return Decimal(str(percent)) == 0

    part_dec = Decimal(str(part))
    pct_dec = Decimal(str(percent))
    actual_pct = (part_dec / tot_dec) * Decimal("100")
    return abs(actual_pct - pct_dec) <= tolerance


def evaluate_evidence_status(
    recompute_matches: bool,
    claim_type: str = "metric",
    invariants_passed: bool = True,
    sample_size_ok: bool = True,
    quality_issues_present: bool = False,
    has_active_assumptions: bool = False,
    data_available: bool = True,
) -> EvidenceStatus:
    """Deterministically assign evidence verification status using formal logic rules."""
    # 1. Non-factual / non-analytical claims
    if claim_type.lower() in ("definition", "suggestion", "question", "next_step"):
        return "not_applicable"

    # 2. Critical failures -> insufficient
    if not data_available or not recompute_matches or not sample_size_ok or not invariants_passed:
        return "insufficient"

    # 3. Caveats / quality issues / explicit assumptions -> partially_supported
    if quality_issues_present or has_active_assumptions:
        return "partially_supported"

    # 4. Verified with zero issues
    return "supported"
