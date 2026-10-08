"""Totals-row detection and exclusion per §8.1.

Rule: rows whose first text cell matches (?i)^\\s*(grand\\s+)?(sub)?total\\b or whose
numeric cells equal the column sums of the rows above. Exclude them and record
drop_totals_row with requires_approval=True.
"""

from decimal import Decimal
import re
from typing import Any, Tuple

from backend.core.ids import generate_id
from backend.ingest.models import TransformationStep

TOTALS_REGEX = re.compile(r"^\s*(grand\s+)?(sub)?total\b", re.IGNORECASE)


def _try_parse_decimal(val: Any) -> Decimal | None:
    """Best-effort decimal conversion for sum comparison."""
    if val is None:
        return None
    s = str(val).strip().replace("$", "").replace("€", "").replace("£", "").replace(",", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def detect_and_drop_totals_rows(
    rows: list[list[Any]],
    column_names: list[str] | None = None,
) -> Tuple[list[list[Any]], list[TransformationStep]]:
    """Identify and filter out totals rows, recording a transformation requiring user approval."""
    if not rows:
        return [], []

    kept_rows: list[list[Any]] = []
    dropped_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        # 1. Check label-based match on first non-empty text cell
        is_totals = False
        first_text = ""
        for cell in row:
            s = str(cell).strip()
            if s:
                first_text = s
                break

        if first_text and TOTALS_REGEX.match(first_text):
            is_totals = True

        # 2. Check sum-based match if near the bottom and has numbers
        if not is_totals and idx > 0 and idx >= len(rows) - 3:
            numeric_cells = [_try_parse_decimal(c) for c in row]
            valid_nums = [n for n in numeric_cells if n is not None]
            if len(valid_nums) >= 2 and kept_rows:
                # Calculate sums of kept_rows so far
                matches = 0
                for col_i, target_val in enumerate(numeric_cells):
                    if target_val is None:
                        continue
                    col_sum = sum(
                        (
                            _try_parse_decimal(r[col_i]) or Decimal(0)
                            for r in kept_rows
                            if col_i < len(r)
                        ),
                        Decimal(0),
                    )
                    if col_sum > 0 and abs(col_sum - target_val) <= Decimal("0.01"):
                        matches += 1
                if matches >= 2:
                    is_totals = True

        if is_totals:
            dropped_rows.append({"original_index": idx, "row": row, "first_text": first_text})
        else:
            kept_rows.append(row)

    transformations: list[TransformationStep] = []
    if dropped_rows:
        transformations.append(
            TransformationStep(
                id=generate_id("tr"),
                operation="drop_totals_row",
                parameters={
                    "dropped_count": len(dropped_rows),
                    "dropped_indices": [d["original_index"] for d in dropped_rows],
                    "labels": [d["first_text"] for d in dropped_rows],
                },
                rows_before=len(rows),
                rows_after=len(kept_rows),
                requires_approval=True,  # Crucial requirement from §8.1
                approved_by_user=None,
            )
        )

    return kept_rows, transformations
