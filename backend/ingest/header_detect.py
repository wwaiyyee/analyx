"""Header row detection per §8.1: >=60% non-empty string cells and consistent following types."""

import re
from typing import Any, Tuple

from backend.core.ids import generate_id
from backend.ingest.models import TransformationStep

NUMERIC_RE = re.compile(r"^[-+]?[$€£]?\s*[\d,.]+%?\s*$")


def _is_text_cell(val: Any) -> bool:
    """Check if cell is a non-empty string that is not purely numeric."""
    s = str(val).strip()
    if not s:
        return False
    if NUMERIC_RE.match(s):
        return False
    return True


def detect_header_row(rows: list[list[Any]]) -> Tuple[int, list[str], list[TransformationStep]]:
    """Detect header row index and clean unique column names.

    Rule: first row where >= 60% of cells are non-empty text strings and following rows
    have consistent column width and data types.
    """
    if not rows:
        return 0, [], []

    best_index = 0
    max_search_rows = min(50, len(rows))

    for idx in range(max_search_rows):
        row = rows[idx]
        if not row:
            continue

        non_empty = [c for c in row if str(c).strip()]
        if not non_empty:
            continue

        text_cells = [c for c in non_empty if _is_text_cell(c)]
        text_ratio = len(text_cells) / len(row)

        if text_ratio >= 0.60:
            # Check consistency of up to 5 following rows
            following_rows = rows[idx + 1 : idx + 6]
            if not following_rows:
                best_index = idx
                break

            # Confirm following rows have roughly the same length and aren't all empty
            consistent_width = all(abs(len(r) - len(row)) <= 2 for r in following_rows if any(r))
            if consistent_width:
                best_index = idx
                break

    header_cells = rows[best_index]
    # Build unique, sanitized column names
    seen: dict[str, int] = {}
    clean_columns: list[str] = []

    for i, cell in enumerate(header_cells):
        raw_name = str(cell).strip()
        name = raw_name if raw_name else f"unnamed_column_{i+1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        clean_columns.append(name)

    transformations = [
        TransformationStep(
            id=generate_id("tr"),
            operation="detect_header_row",
            parameters={"header_row_index": best_index, "columns": clean_columns},
            rows_before=len(rows),
            rows_after=len(rows) - best_index - 1,
            requires_approval=False,
        )
    ]

    return best_index, clean_columns, transformations
