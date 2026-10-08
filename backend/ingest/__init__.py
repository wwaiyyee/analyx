"""Ingestion module — file reading, normalization, and quality validation."""

from backend.ingest.dates import infer_date_day_first, parse_date_column, parse_date_value
from backend.ingest.header_detect import detect_header_row
from backend.ingest.locale import (
    infer_column_locale_convention,
    parse_locale_number,
    parse_numeric_column,
)
from backend.ingest.models import (
    ColumnProfile,
    ColumnSchema,
    QualityIssue,
    QualityReport,
    TransformationStep,
)
from backend.ingest.normalize import normalize_dataset
from backend.ingest.reader import read_csv_raw, read_file, read_xlsx_raw
from backend.ingest.totals_rows import detect_and_drop_totals_rows

__all__ = [
    "ColumnSchema",
    "TransformationStep",
    "QualityIssue",
    "ColumnProfile",
    "QualityReport",
    "read_file",
    "read_csv_raw",
    "read_xlsx_raw",
    "detect_header_row",
    "detect_and_drop_totals_rows",
    "parse_locale_number",
    "parse_numeric_column",
    "infer_column_locale_convention",
    "parse_date_column",
    "parse_date_value",
    "infer_date_day_first",
    "normalize_dataset",
]
