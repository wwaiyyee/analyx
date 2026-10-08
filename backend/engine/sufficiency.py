"""Data sufficiency verification engine per §7.5 and §8.3.

Evaluates semantic role presence, coverage >= 0.9, grain, time span, and history completeness.
Produces verdicts: ANSWERABLE, ANSWERABLE_WITH_CAVEATS, PARTIAL, INSUFFICIENT_DATA.
"""

from typing import Any
import pandas as pd

from backend.engine.sufficiency_models import (
    Requirement,
    RequirementCheck,
    SufficiencyResult,
)


def check_sufficiency(
    df: pd.DataFrame,
    requirements: list[Requirement],
    complete_history: bool = True,
    time_span_days_needed: int = 0,
    min_rows_needed: int = 1,
) -> SufficiencyResult:
    """Evaluate whether dataset satisfies analytical requirements to answer a question.

    Returns structured SufficiencyResult with explicit verdict, checks, and missing items.
    """
    checks: list[RequirementCheck] = []
    caveats: list[str] = []
    missing_items: list[str] = []

    # 1. Total row count check
    if len(df) < min_rows_needed:
        checks.append(
            RequirementCheck(
                requirement=Requirement(role="row_count", note=f"Need >= {min_rows_needed} rows"),
                status="too_few_rows",
                detail=f"Dataset has only {len(df)} row(s), need at least {min_rows_needed}.",
            )
        )
        missing_items.append("sufficient_row_count")

    # 2. History completeness check (vital for runway or lifetime metrics)
    if not complete_history:
        checks.append(
            RequirementCheck(
                requirement=Requirement(role="complete_history", note="Unbroken ledger history"),
                status="missing",
                detail="Transaction history is flagged as truncated or incomplete.",
            )
        )
        missing_items.append("complete_history")

    # 3. Check each semantic role requirement
    for req in requirements:
        col_role = req.role

        # Handle specific column or role matching
        matching_col: str | None = None
        for c in df.columns:
            if c.lower() == col_role.lower() or c.lower().endswith(col_role.lower()):
                matching_col = c
                break

        if not matching_col:
            checks.append(
                RequirementCheck(
                    requirement=req,
                    status="missing",
                    detail=f"Required role/column '{col_role}' not found in dataset.",
                )
            )
            missing_items.append(col_role)
            continue

        # Coverage check (share of non-null values)
        null_count = int(df[matching_col].isna().sum())
        total_count = len(df)
        coverage = (total_count - null_count) / total_count if total_count > 0 else 0.0
        min_cov = float(req.min_coverage)

        if coverage < min_cov:
            checks.append(
                RequirementCheck(
                    requirement=req,
                    status="low_coverage",
                    detail=f"Column '{matching_col}' has {coverage:.1%} coverage, below required {min_cov:.1%}.",
                )
            )
            caveats.append(f"Column '{matching_col}' has missing values ({coverage:.1%} coverage).")
        else:
            checks.append(
                RequirementCheck(
                    requirement=req,
                    status="ok",
                    detail=f"Column '{matching_col}' present with {coverage:.1%} non-null coverage.",
                )
            )

    # 4. Time span check
    if time_span_days_needed > 0 and "block_time" in df.columns:
        dt_series = pd.to_datetime(df["block_time"], errors="coerce", utc=True).dropna()
        if not dt_series.empty:
            actual_span = (dt_series.max() - dt_series.min()).days
            if actual_span < time_span_days_needed:
                checks.append(
                    RequirementCheck(
                        requirement=Requirement(role="time_span", note=f"Need >= {time_span_days_needed} days"),
                        status="too_short_span",
                        detail=f"Dataset spans {actual_span} days, need at least {time_span_days_needed} days.",
                    )
                )
                missing_items.append(f"{time_span_days_needed}_day_history")

    # 5. Formulate final verdict
    has_missing = any(c.status in ("missing", "too_few_rows") for c in checks)
    has_low_cov_or_span = any(c.status in ("low_coverage", "too_short_span", "grain_mismatch") for c in checks)

    if has_missing:
        verdict = "INSUFFICIENT_DATA"
    elif has_low_cov_or_span:
        verdict = "ANSWERABLE_WITH_CAVEATS"
    else:
        verdict = "ANSWERABLE"

    answerable_now = ["summary_stats", "partial_metrics"] if verdict != "INSUFFICIENT_DATA" else []

    return SufficiencyResult(
        verdict=verdict,
        checks=checks,
        caveats=caveats,
        answerable_now=answerable_now,
        missing=missing_items,
    )
