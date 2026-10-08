"""Unit tests for time anchor policy and window resolution."""

from datetime import date, datetime, timezone
import pytest

from backend.core.time_anchor import (
    get_last_complete_month,
    get_prior_period,
    is_month_complete,
    last_day_of_month,
    resolve_anchor,
    resolve_window,
    to_utc_datetime,
)


def test_last_day_of_month() -> None:
    assert last_day_of_month(2026, 1) == 31
    assert last_day_of_month(2026, 2) == 28  # non leap
    assert last_day_of_month(2024, 2) == 29  # leap year
    assert last_day_of_month(2026, 4) == 30
    assert last_day_of_month(2026, 12) == 31


def test_is_month_complete() -> None:
    # Mid-month anchor
    mid_oct = date(2026, 10, 15)
    assert not is_month_complete(mid_oct, 2026, 10)
    assert is_month_complete(mid_oct, 2026, 9)

    # Last day anchor
    end_sep = date(2026, 9, 30)
    assert is_month_complete(end_sep, 2026, 9)
    assert not is_month_complete(end_sep, 2026, 10)

    # First day of next month is complete for previous month
    nov_1 = date(2026, 11, 1)
    assert is_month_complete(nov_1, 2026, 10)


def test_get_last_complete_month_mid_month() -> None:
    # On Oct 15, 2026, last complete month is Sept 2026
    anchor = date(2026, 10, 15)
    start, end = get_last_complete_month(anchor)
    assert start == date(2026, 9, 1)
    assert end == date(2026, 9, 30)


def test_get_last_complete_month_month_end() -> None:
    # On Sept 30, 2026, Sept is complete!
    anchor = date(2026, 9, 30)
    start, end = get_last_complete_month(anchor)
    assert start == date(2026, 9, 1)
    assert end == date(2026, 9, 30)


def test_get_last_complete_month_year_boundary() -> None:
    # On Jan 10, 2026, last complete month is Dec 2025
    anchor = date(2026, 1, 10)
    start, end = get_last_complete_month(anchor)
    assert start == date(2025, 12, 1)
    assert end == date(2025, 12, 31)


def test_resolve_anchor() -> None:
    data = [
        "2026-05-01T10:00:00Z",
        "2026-09-15T12:00:00Z",
        None,
        "<NA>",
        "2026-08-20T08:00:00Z",
    ]
    anchor = resolve_anchor(data)
    assert anchor == datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError):
        resolve_anchor([None, "<NA>"])


def test_get_prior_period() -> None:
    # Prior month for September 2026 is August 2026
    start = date(2026, 9, 1)
    end = date(2026, 9, 30)
    p_start, p_end = get_prior_period(start, end)
    assert p_start == date(2026, 8, 1)
    assert p_end == date(2026, 8, 31)

    # Prior month for January 2026 is December 2025
    jan_start = date(2026, 1, 1)
    jan_end = date(2026, 1, 31)
    p_jan_start, p_jan_end = get_prior_period(jan_start, jan_end)
    assert p_jan_start == date(2025, 12, 1)
    assert p_jan_end == date(2025, 12, 31)


def test_resolve_window_last_month() -> None:
    anchor = datetime(2026, 10, 15, tzinfo=timezone.utc)
    win = resolve_window(anchor, "last_month")
    assert win.start_date == date(2026, 9, 1)
    assert win.end_date == date(2026, 9, 30)
    assert win.is_complete is True
    assert "September 2026 (complete)" in win.label


def test_resolve_window_mtd_partial() -> None:
    anchor = datetime(2026, 10, 15, tzinfo=timezone.utc)
    win = resolve_window(anchor, "mtd")
    assert win.start_date == date(2026, 10, 1)
    assert win.end_date == date(2026, 10, 15)
    assert win.is_complete is False
    assert "partial" in win.label


def test_resolve_window_last_3_months() -> None:
    anchor = datetime(2026, 10, 15, tzinfo=timezone.utc)
    win = resolve_window(anchor, "last_3_months")
    # Last complete month is September, so 3 complete months = July, August, September 2026
    assert win.start_date == date(2026, 7, 1)
    assert win.end_date == date(2026, 9, 30)
    assert win.is_complete is True
