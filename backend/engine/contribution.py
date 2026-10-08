"""Contribution analysis per §8.5: segment deltas, share of change, ranking by |Δ|, and Other grouping."""

from decimal import Decimal
from typing import Any, Tuple
from pydantic import BaseModel, Field


class SegmentContribution(BaseModel):
    """Calculated analytical contribution metrics for a single segment."""

    segment: str
    current_value: str  # Decimal string e.g. "3496471.00"
    baseline_value: str
    delta: str
    share_of_change_pct: str | None  # May exceed 100% or be negative
    baseline_share_pct: str
    is_concentrated: bool = False


class ContributionReport(BaseModel):
    """Overall breakdown of drivers of metric change."""

    dimension: str
    metric: str
    current_total: str
    baseline_total: str
    delta_total: str
    segments: list[SegmentContribution] = Field(default_factory=list)
    has_other_grouping: bool = False
    other_segment_count: int = 0


def analyze_contribution(
    segment_data: list[dict[str, Any]],
    dimension_col: str,
    current_metric_col: str,
    baseline_metric_col: str,
    row_count_col: str | None = None,
    group_other: bool = True,
) -> ContributionReport:
    """Compute exact contribution analysis per segment.

    Rules from §8.5:
    - value_s^c, value_s^b per segment s
    - Δ_s = value_s^c - value_s^b
    - Δ_total = Σ Δ_s
    - share_of_change = Δ_s / Δ_total (reported as percentage; may exceed 100% or be negative)
    - baseline_share = value_s^b / Σ value^b
    - Rank by |Δ_s| descending
    - Flag concentrated if share_of_change >= baseline_share + 0.15 (15 percentage points)
    - Segments < 30 rows and < 1% of measure grouped into 'Other'
    """
    total_curr = Decimal("0")
    total_base = Decimal("0")
    raw_segments: list[dict[str, Any]] = []

    for row in segment_data:
        seg_name = str(row.get(dimension_col, "Unknown"))
        c_val = Decimal(str(row.get(current_metric_col) or 0))
        b_val = Decimal(str(row.get(baseline_metric_col) or 0))
        rows_cnt = int(row.get(row_count_col, 0)) if row_count_col else 30

        total_curr += c_val
        total_base += b_val
        raw_segments.append({
            "segment": seg_name,
            "curr": c_val,
            "base": b_val,
            "rows": rows_cnt,
            "delta": c_val - b_val,
        })

    delta_total = total_curr - total_base

    # Check for 'Other' grouping threshold (>= 30 rows AND >= 1% of measure in either window)
    kept_segments: list[dict[str, Any]] = []
    other_curr = Decimal("0")
    other_base = Decimal("0")
    other_count = 0

    thresh_curr = total_curr * Decimal("0.01") if total_curr > 0 else Decimal("0")
    thresh_base = total_base * Decimal("0.01") if total_base > 0 else Decimal("0")

    for s in raw_segments:
        is_small = (
            group_other
            and s["rows"] < 30
            and s["curr"] < thresh_curr
            and s["base"] < thresh_base
        )
        if is_small:
            other_curr += s["curr"]
            other_base += s["base"]
            other_count += 1
        else:
            kept_segments.append(s)

    if other_count > 0:
        kept_segments.append({
            "segment": "Other",
            "curr": other_curr,
            "base": other_base,
            "rows": 0,
            "delta": other_curr - other_base,
        })

    # Rank by |Δ_s| descending
    kept_segments.sort(key=lambda s: abs(s["delta"]), reverse=True)

    result_segments: list[SegmentContribution] = []
    for s in kept_segments:
        curr = s["curr"]
        base = s["base"]
        delta = s["delta"]

        # Share of change
        if delta_total != Decimal("0"):
            share = (delta / delta_total) * Decimal("100")
            share_str = f"{share:.2f}"
        else:
            share = None
            share_str = None

        # Baseline share
        if total_base > Decimal("0"):
            base_share = (base / total_base) * Decimal("100")
            base_share_str = f"{base_share:.2f}"
        else:
            base_share = Decimal("0")
            base_share_str = "0.00"

        # Concentrated flag: share_of_change >= baseline_share + 15%
        is_concentrated = False
        if share is not None and base_share is not None:
            if share >= (base_share + Decimal("15.0")):
                is_concentrated = True

        result_segments.append(
            SegmentContribution(
                segment=s["segment"],
                current_value=f"{curr:.2f}",
                baseline_value=f"{base:.2f}",
                delta=f"{delta:.2f}",
                share_of_change_pct=share_str,
                baseline_share_pct=base_share_str,
                is_concentrated=is_concentrated,
            )
        )

    return ContributionReport(
        dimension=dimension_col,
        metric=current_metric_col.replace("current_", ""),
        current_total=f"{total_curr:.2f}",
        baseline_total=f"{total_base:.2f}",
        delta_total=f"{delta_total:.2f}",
        segments=result_segments,
        has_other_grouping=other_count > 0,
        other_segment_count=other_count,
    )
