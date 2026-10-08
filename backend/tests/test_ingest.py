"""Unit tests for file ingestion, header detection, totals rows, locale numbers, and dates."""

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import pytest

from backend.ingest.dates import infer_date_day_first, parse_date_column
from backend.ingest.header_detect import detect_header_row
from backend.ingest.locale import infer_column_locale_convention, parse_locale_number
from backend.ingest.normalize import normalize_dataset
from backend.ingest.reader import detect_csv_delimiter, read_file
from backend.ingest.totals_rows import detect_and_drop_totals_rows


def test_reader_delimiter_detection() -> None:
    csv_comma = "id,name,amount\n1,Alice,100\n2,Bob,200\n"
    assert detect_csv_delimiter(csv_comma) == ","

    csv_semi = "id;name;amount\n1;Alice;100\n2;Bob;200\n"
    assert detect_csv_delimiter(csv_semi) == ";"

    csv_tab = "id\tname\tamount\n1\tAlice\t100\n2\tBob\t200\n"
    assert detect_csv_delimiter(csv_tab) == "\t"


def test_header_detection_with_title_row() -> None:
    rows = [
        ["Monthly Financial Report - Company XYZ"],  # Row 0: Title row
        ["Date", "Category", "Amount", "Status"],   # Row 1: Real header row
        ["2026-01-01", "Ops", "100.00", "Paid"],
        ["2026-01-02", "Dev", "250.00", "Paid"],
        ["2026-01-03", "Sales", "300.00", "Pending"],
    ]

    header_idx, col_names, steps = detect_header_row(rows)
    assert header_idx == 1
    assert col_names == ["Date", "Category", "Amount", "Status"]
    assert len(steps) == 1
    assert steps[0].operation == "detect_header_row"


def test_totals_row_detection() -> None:
    rows = [
        ["2026-01-01", "Sales", "100.00"],
        ["2026-01-02", "Sales", "200.00"],
        ["Grand Total", "", "300.00"],
    ]

    clean_rows, steps = detect_and_drop_totals_rows(rows)
    assert len(clean_rows) == 2
    assert len(steps) == 1
    assert steps[0].operation == "drop_totals_row"
    assert steps[0].requires_approval is True  # Mandatory requirement from §8.1
    assert steps[0].parameters["dropped_count"] == 1


def test_locale_numbers_en_and_de() -> None:
    # US format
    assert parse_locale_number("$1,234.50", "en_US") == Decimal("1234.50")
    assert parse_locale_number("(1,234.50)", "en_US") == Decimal("-1234.50")
    assert parse_locale_number("12.5%", "en_US") == Decimal("0.125")

    # German / European format
    assert parse_locale_number("1.234,50 €", "de_DE") == Decimal("1234.50")
    assert parse_locale_number("(1.234,50)", "de_DE") == Decimal("-1234.50")

    # Convention inference
    assert infer_column_locale_convention(["$1,234.50", "$5,000.00"]) == "en_US"
    assert infer_column_locale_convention(["1.234,50 €", "5.000,00 €"]) == "de_DE"


def test_dates_day_first_vs_month_first() -> None:
    # Day > 12 settles day-first
    day_first, is_ambig = infer_date_day_first(["25/01/2026", "28/02/2026", "10/03/2026"])
    assert day_first is True
    assert is_ambig is False

    # Month > 12 settles month-first
    day_first_2, is_ambig_2 = infer_date_day_first(["01/25/2026", "02/28/2026"])
    assert day_first_2 is False
    assert is_ambig_2 is False

    # Ambiguous when both <= 12
    _, is_ambig_3 = infer_date_day_first(["01/02/2026", "03/04/2026"])
    assert is_ambig_3 is True


def test_full_normalize_pipeline_synthetic() -> None:
    raw_csv = (
        "Internal Sales Report Q3\n"
        "Date,Customer,Amount,Active\n"
        '2026-07-01,Alpha,"$1,500.00",true\n'
        '2026-07-15,Beta,"$2,250.50",false\n'
        '2026-08-30,Gamma,"$3,000.00",true\n'
        'Total,,"$6,750.50",\n'
    ).encode("utf-8")

    with tempfile.TemporaryDirectory() as tmp_dir:
        df, steps, schemas, c_hash, parquet_path, anchor = normalize_dataset(
            filename="sales.csv",
            content=raw_csv,
            dataset_id="ds_test123",
        )

        assert len(df) == 3  # Totals row dropped
        assert len(c_hash) == 64
        assert Path(parquet_path).exists()
        assert anchor == datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)

        # Check schemas
        col_map = {s.name: s.dtype for s in schemas}
        assert col_map["Date"] == "datetime"
        assert col_map["Amount"] == "decimal"
        assert col_map["Active"] == "bool"

        # Check recorded steps include drop_totals_row with requires_approval
        drop_steps = [s for s in steps if s.operation == "drop_totals_row"]
        assert len(drop_steps) == 1
        assert drop_steps[0].requires_approval is True
