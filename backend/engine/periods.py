"""Period resolution helpers for period-over-period comparisons per §8.5."""

from datetime import date, datetime
from typing import Tuple

from backend.core.time_anchor import get_last_complete_month, get_prior_period, to_utc_datetime
from backend.engine.models import Comparison, TimeWindow


def build_period_over_period_windows(
    anchor: datetime | date,
    time_column: str,
    window_type: str = "last_month",
) -> Tuple[TimeWindow, TimeWindow, Comparison]:
    """Resolve current and prior baseline TimeWindow objects for period-over-period comparison."""
    anchor_dt = to_utc_datetime(anchor)
    anchor_date = anchor_dt.date()

    if window_type in ("last_month", "last_complete_month"):
        curr_start, curr_end = get_last_complete_month(anchor_date)
        base_start, base_end = get_prior_period(curr_start, curr_end)

        curr_window = TimeWindow(
            column=time_column,
            start=curr_start,
            end=curr_end,
            grain="month",
        )
        base_window = TimeWindow(
            column=time_column,
            start=base_start,
            end=base_end,
            grain="month",
        )
        comparison = Comparison(
            kind="period_over_period",
            baseline=base_window,
        )
        return curr_window, base_window, comparison

    raise ValueError(f"Unsupported comparison window type: {window_type}")
