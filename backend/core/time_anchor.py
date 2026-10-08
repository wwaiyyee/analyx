"""Time anchor policy and calendar window resolution.

Per blueprint §8.3 / §8.4:
- Anchor = max(date column) in the data (on-chain: latest block_time).
- "Last month" = the last COMPLETE calendar month ending on or before the anchor.
- A month is complete only if the anchor is on or after its last day.
- Partial periods are excluded from period-over-period comparisons and flagged.
- The resolved window MUST be explicitly stated.
"""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class TimeWindow:
    start_date: date
    end_date: date
    is_complete: bool
    label: str
    anchor: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "is_complete": self.is_complete,
            "label": self.label,
            "anchor": self.anchor.isoformat(),
        }


def to_utc_datetime(val: Any) -> datetime:
    """Normalize string, date, or datetime into UTC datetime."""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, date):
        return datetime.combine(val, time.min, tzinfo=timezone.utc)
    if isinstance(val, (int, float)):
        # Epoch timestamp in seconds or milliseconds
        if val > 1e11:  # ms
            return datetime.fromtimestamp(val / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(val, tz=timezone.utc)
    if isinstance(val, str):
        # Strip trailing Z for fromisoformat compatibility in older versions
        s = val.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            # Fallback for plain YYYY-MM-DD
            d = date.fromisoformat(val[:10])
            return datetime.combine(d, time.min, tzinfo=timezone.utc)
    raise TypeError(f"Cannot convert {type(val).__name__} to UTC datetime")


def resolve_anchor(timestamps: Iterable[Any]) -> datetime:
    """Find maximum timestamp in dataset, normalized to UTC datetime.

    Raises ValueError if timestamps is empty.
    """
    latest: datetime | None = None
    for item in timestamps:
        if item is None:
            continue
        # Skip pandas/numpy missing markers
        if str(item) in ("<NA>", "NaN", "nan", "NaT", "None"):
            continue
        try:
            dt = to_utc_datetime(item)
            if latest is None or dt > latest:
                latest = dt
        except (ValueError, TypeError):
            continue

    if latest is None:
        raise ValueError("Cannot resolve anchor: no valid dates found in data")
    return latest


def last_day_of_month(year: int, month: int) -> int:
    """Return the last calendar day of the given month (28, 29, 30, or 31)."""
    return calendar.monthrange(year, month)[1]


def is_month_complete(anchor: datetime | date, year: int, month: int) -> bool:
    """A month is complete only if the anchor is on or after its last calendar day."""
    anchor_date = anchor.date() if isinstance(anchor, datetime) else anchor
    month_end_date = date(year, month, last_day_of_month(year, month))
    return anchor_date >= month_end_date


def get_last_complete_month(anchor: datetime | date) -> tuple[date, date]:
    """Find the last complete calendar month on or before anchor.

    If anchor is on or after the last day of its month, that month is complete.
    Otherwise, the preceding month is the last complete month.
    """
    anchor_date = anchor.date() if isinstance(anchor, datetime) else anchor
    year = anchor_date.year
    month = anchor_date.month

    if is_month_complete(anchor_date, year, month):
        target_year, target_month = year, month
    else:
        # Step back one month
        if month == 1:
            target_year, target_month = year - 1, 12
        else:
            target_year, target_month = year, month - 1

    start = date(target_year, target_month, 1)
    end = date(target_year, target_month, last_day_of_month(target_year, target_month))
    return start, end


def get_prior_period(start: date, end: date) -> tuple[date, date]:
    """Calculate the immediately preceding period of identical duration.

    For calendar months (1st to last day of month), returns the previous calendar month.
    Otherwise returns [start - span, start - 1 day].
    """
    if start.day == 1 and end.day == last_day_of_month(end.year, end.month) and start.month == end.month:
        # Exactly one calendar month
        year, month = start.year, start.month
        prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
        prev_start = date(prev_year, prev_month, 1)
        prev_end = date(prev_year, prev_month, last_day_of_month(prev_year, prev_month))
        return prev_start, prev_end

    delta = end - start
    prior_end = start.fromordinal(start.toordinal() - 1)
    prior_start = prior_end.fromordinal(prior_end.toordinal() - delta.days)
    return prior_start, prior_end


def resolve_window(
    anchor: datetime | date,
    window_type: str = "last_month",
    start_override: date | None = None,
    end_override: date | None = None,
) -> TimeWindow:
    """Resolve a semantic time window against the dataset time anchor.

    Supported window types:
    - 'last_month' / 'last_complete_month': Last complete calendar month
    - 'mtd' / 'month_to_date': 1st of current month to anchor (is_complete = False unless anchor is last day)
    - 'last_3_months': 3 complete calendar months ending with the last complete month
    - 'custom': Explicit start and end overrides
    """
    anchor_dt = to_utc_datetime(anchor)
    anchor_date = anchor_dt.date()

    if window_type in ("last_month", "last_complete_month"):
        start, end = get_last_complete_month(anchor_date)
        month_name = calendar.month_name[start.month]
        label = f"{month_name} {start.year} (complete)"
        return TimeWindow(
            start_date=start,
            end_date=end,
            is_complete=True,
            label=label,
            anchor=anchor_dt,
        )

    if window_type in ("mtd", "month_to_date"):
        start = date(anchor_date.year, anchor_date.month, 1)
        end = anchor_date
        complete = is_month_complete(anchor_date, anchor_date.year, anchor_date.month)
        month_name = calendar.month_name[start.month]
        status = "complete" if complete else "partial"
        label = f"{month_name} 1–{end.day}, {end.year} ({status})"
        return TimeWindow(
            start_date=start,
            end_date=end,
            is_complete=complete,
            label=label,
            anchor=anchor_dt,
        )

    if window_type == "last_3_months":
        last_comp_start, last_comp_end = get_last_complete_month(anchor_date)
        # Go back 2 more months from last_comp_start
        y, m = last_comp_start.year, last_comp_start.month
        for _ in range(2):
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        first_start = date(y, m, 1)
        m1 = calendar.month_abbr[first_start.month]
        m2 = calendar.month_abbr[last_comp_end.month]
        label = f"{m1}–{m2} {last_comp_end.year} (3 complete months)"
        return TimeWindow(
            start_date=first_start,
            end_date=last_comp_end,
            is_complete=True,
            label=label,
            anchor=anchor_dt,
        )

    if window_type == "custom" and start_override and end_override:
        complete = end_override <= anchor_date
        label = f"{start_override.isoformat()} to {end_override.isoformat()}"
        return TimeWindow(
            start_date=start_override,
            end_date=end_override,
            is_complete=complete,
            label=label,
            anchor=anchor_dt,
        )

    raise ValueError(f"Unsupported window type: {window_type}")
