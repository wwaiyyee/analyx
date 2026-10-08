"""Date parsing and day-first vs month-first inference per §8.1.

Rule: infer day-first vs month-first from the whole column (any value with a part > 12 settles it).
If still ambiguous, record an assumption and flag for question card.
"""

from datetime import date, datetime, timezone
import re
from typing import Any, Tuple

from dateutil import parser as date_parser

from backend.core.ids import generate_id
from backend.ingest.models import TransformationStep

ISO_DATE_RE = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}")
SLASH_DATE_RE = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})")


def infer_date_day_first(values: list[str]) -> Tuple[bool, bool]:
    """Inspect date strings across column to determine day-first vs month-first.

    Returns: (day_first, is_ambiguous)
    """
    has_day_first_indicator = False
    has_month_first_indicator = False

    for val in values:
        s = val.strip()
        if not s or ISO_DATE_RE.match(s):
            continue

        m = SLASH_DATE_RE.match(s)
        if m:
            p1, p2, _ = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if p1 > 12 and p2 <= 12:
                has_day_first_indicator = True
            elif p2 > 12 and p1 <= 12:
                has_month_first_indicator = True

    if has_day_first_indicator and not has_month_first_indicator:
        return True, False
    if has_month_first_indicator and not has_day_first_indicator:
        return False, False

    # Ambiguous: both components <= 12 in all samples (or conflicting)
    return False, True


def parse_date_value(val: Any, day_first: bool = False) -> datetime | None:
    """Parse single cell into UTC datetime."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("null", "none", "nan", "nat", "<na>"):
        return None

    # Handle numeric epoch timestamp
    if s.isdigit() and len(s) in (10, 13):
        ts = int(s)
        if len(s) == 13:
            ts = ts / 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    try:
        dt = date_parser.parse(s, dayfirst=day_first)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def parse_date_column(
    col_name: str,
    values: list[Any],
) -> Tuple[list[datetime | None], bool, bool, list[TransformationStep]]:
    """Parse entire column into normalized UTC datetimes and record transformation step."""
    str_samples = [str(v).strip() for v in values if v is not None and str(v).strip()]
    day_first, is_ambiguous = infer_date_day_first(str_samples)

    parsed = [parse_date_value(v, day_first=day_first) for v in values]

    convention = "day_first (DD/MM)" if day_first else "month_first (MM/DD)"
    transformations = [
        TransformationStep(
            id=generate_id("tr"),
            operation="parse_date_format",
            parameters={
                "column": col_name,
                "day_first": day_first,
                "convention": convention,
                "is_ambiguous": is_ambiguous,
            },
            rows_before=len(values),
            rows_after=len(values),
            requires_approval=False,
        )
    ]

    return parsed, day_first, is_ambiguous, transformations
