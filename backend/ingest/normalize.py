"""Full normalization pipeline composing reader, header detect, totals drop, locale numbers, and dates."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Tuple

import pandas as pd

from backend.config import settings
from backend.core.hashing import canonical_table_hash
from backend.core.ids import generate_id
from backend.core.time_anchor import resolve_anchor
from backend.ingest.dates import parse_date_column
from backend.ingest.header_detect import detect_header_row
from backend.ingest.locale import parse_numeric_column
from backend.ingest.models import ColumnSchema, TransformationStep
from backend.ingest.reader import read_file
from backend.ingest.totals_rows import detect_and_drop_totals_rows

BOOLEAN_TRUE_VALUES = {"true", "yes", "1", "t", "y"}
BOOLEAN_FALSE_VALUES = {"false", "no", "0", "f", "n"}


def _infer_column_type(values: list[Any]) -> str:
    """Infer column type: 'date', 'decimal', 'int', 'bool', or 'string'."""
    non_empty = [str(v).strip() for v in values if v is not None and str(v).strip()]
    if not non_empty:
        return "string"

    # 1. Check boolean
    if all(s.lower() in BOOLEAN_TRUE_VALUES | BOOLEAN_FALSE_VALUES for s in non_empty):
        return "bool"

    # 2. Check date
    date_matches = 0
    for s in non_empty[:50]:
        if any(c in s for c in "-/.") and any(d in s for d in "0123456789"):
            # Simple heuristic before full parse
            if len(s) >= 8 and sum(c.isdigit() for c in s) >= 4:
                date_matches += 1
    if len(non_empty) > 0 and date_matches / min(50, len(non_empty)) >= 0.70:
        return "date"

    # 3. Check number
    num_matches = 0
    for s in non_empty[:50]:
        cleaned = (
            s.replace("$", "")
            .replace("€", "")
            .replace("£", "")
            .replace("%", "")
            .replace(",", "")
            .replace(" ", "")
            .strip()
        )
        if cleaned.replace(".", "", 1).replace("-", "", 1).isdigit():
            num_matches += 1
    if len(non_empty) > 0 and num_matches / min(50, len(non_empty)) >= 0.70:
        if all(
            s.replace(",", "").replace(" ", "").lstrip("-").isdigit()
            for s in non_empty
            if s.isdigit()
        ):
            return "int"
        return "decimal"

    return "string"


def normalize_dataset(
    filename: str,
    content: bytes,
    dataset_id: str | None = None,
) -> Tuple[pd.DataFrame, list[TransformationStep], list[ColumnSchema], str, str, datetime | None]:
    """Execute complete normalization pipeline on raw file bytes.

    Returns:
    - df: Normalized pandas DataFrame
    - transformations: List of TransformationStep applied
    - schemas: List of ColumnSchema
    - content_hash: SHA-256 canonical table hash
    - parquet_path: Saved Parquet file location
    - time_anchor: Resolved latest datetime in the dataset (if any date column exists)
    """
    if dataset_id is None:
        dataset_id = generate_id("ds")

    all_transformations: list[TransformationStep] = []

    # 1. Read raw rows and detect sheet/format
    raw_rows, read_meta, read_steps = read_file(filename, content)
    all_transformations.extend(read_steps)

    # 2. Detect header row
    header_idx, col_names, header_steps = detect_header_row(raw_rows)
    all_transformations.extend(header_steps)

    data_rows = raw_rows[header_idx + 1 :]

    # 3. Detect and drop totals rows (requires_approval=True)
    clean_rows, totals_steps = detect_and_drop_totals_rows(data_rows, col_names)
    all_transformations.extend(totals_steps)

    # Pad any ragged rows to col_names length
    padded_rows: list[list[Any]] = []
    for r in clean_rows:
        if len(r) < len(col_names):
            padded_rows.append(r + [""] * (len(col_names) - len(r)))
        else:
            padded_rows.append(r[: len(col_names)])

    # 4. Infer types and parse each column
    column_data: dict[str, list[Any]] = {}
    schemas: list[ColumnSchema] = []
    all_dates: list[datetime] = []

    for col_idx, col_name in enumerate(col_names):
        col_raw = [row[col_idx] if col_idx < len(row) else "" for row in padded_rows]
        inferred = _infer_column_type(col_raw)

        if inferred == "date":
            parsed_dates, _, is_ambiguous, date_steps = parse_date_column(col_name, col_raw)
            column_data[col_name] = parsed_dates
            all_transformations.extend(date_steps)
            schemas.append(ColumnSchema(name=col_name, dtype="datetime", nullable=True))
            for dt in parsed_dates:
                if dt is not None:
                    all_dates.append(dt)

        elif inferred in ("decimal", "int"):
            parsed_nums, _, num_steps = parse_numeric_column(col_name, col_raw)
            all_transformations.extend(num_steps)
            # Store numeric column as string or float for DataFrame, but preserve decimal strings
            column_data[col_name] = [str(n) if n is not None else None for n in parsed_nums]
            schemas.append(
                ColumnSchema(
                    name=col_name,
                    dtype="decimal" if inferred == "decimal" else "int",
                    nullable=True,
                )
            )

        elif inferred == "bool":
            parsed_bools = [
                True
                if str(v).strip().lower() in BOOLEAN_TRUE_VALUES
                else (False if str(v).strip().lower() in BOOLEAN_FALSE_VALUES else None)
                for v in col_raw
            ]
            column_data[col_name] = parsed_bools
            schemas.append(ColumnSchema(name=col_name, dtype="bool", nullable=True))

        else:
            column_data[col_name] = [str(v).strip() if v is not None else None for v in col_raw]
            schemas.append(ColumnSchema(name=col_name, dtype="string", nullable=True))

    df = pd.DataFrame(column_data)

    # 5. Compute canonical table hash
    c_hash = canonical_table_hash(df, columns=col_names)

    # 6. Resolve time anchor if any date columns exist
    t_anchor: datetime | None = None
    if all_dates:
        try:
            t_anchor = resolve_anchor(all_dates)
        except ValueError:
            t_anchor = None

    # 7. Write normalized parquet file
    out_dir = Path(settings.data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = str(out_dir / f"{dataset_id}_{c_hash[:16]}.parquet")

    # Format datetime columns for pyarrow
    df_parquet = df.copy()
    for col_idx, col_name in enumerate(col_names):
        if schemas[col_idx].dtype == "datetime":
            df_parquet[col_name] = pd.to_datetime(df_parquet[col_name], utc=True)

    df_parquet.to_parquet(parquet_path, engine="pyarrow", index=False)

    return df, all_transformations, schemas, c_hash, parquet_path, t_anchor
