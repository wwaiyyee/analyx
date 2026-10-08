"""Locale number parsing per §8.1: formats 1,234.50, 1.234,50, $1,234, (1,234) negatives, 12%."""

from decimal import Decimal, InvalidOperation
import re
from typing import Any, Tuple

from backend.core.ids import generate_id
from backend.ingest.models import TransformationStep

PAREN_NEGATIVE_RE = re.compile(r"^\((.+)\)$")
PERCENT_RE = re.compile(r"^(.*?)\s*%$")
CURRENCY_SYMBOLS = ["$", "€", "£", "¥", "USDT", "USDC", "SOL"]


def clean_currency_and_signs(val: str) -> Tuple[str, bool, bool]:
    """Strip currency symbols, detect parentheses negative, and percentage flag.

    Returns: (cleaned_str, is_negative, is_percent)
    """
    s = val.strip()
    is_percent = False
    is_negative = False

    # Check parentheses negative e.g. (1,234)
    paren_match = PAREN_NEGATIVE_RE.match(s)
    if paren_match:
        is_negative = True
        s = paren_match.group(1).strip()

    # Check percentage
    pct_match = PERCENT_RE.match(s)
    if pct_match:
        is_percent = True
        s = pct_match.group(1).strip()

    # Strip currency symbols and whitespace
    for sym in CURRENCY_SYMBOLS:
        s = s.replace(sym, "").strip()

    if s.startswith("-"):
        is_negative = True
        s = s[1:].strip()
    elif s.startswith("+"):
        s = s[1:].strip()

    return s, is_negative, is_percent


def infer_column_locale_convention(values: list[str]) -> str:
    """Infer whether column uses 'en_US' (1,234.50) or 'de_DE' (1.234,50).

    Returns 'en_US' or 'de_DE'.
    """
    en_score = 0
    de_score = 0

    for raw in values:
        s, _, _ = clean_currency_and_signs(str(raw))
        if not s:
            continue

        # Both dot and comma present
        if "." in s and "," in s:
            # 1,234.50 -> en_US
            if s.rfind(".") > s.rfind(","):
                en_score += 10
            # 1.234,50 -> de_DE
            elif s.rfind(",") > s.rfind("."):
                de_score += 10
        elif "," in s and "." not in s:
            # e.g. 1234,50 (comma decimal) vs 1,234 (comma thousand)
            parts = s.split(",")
            if len(parts) == 2 and len(parts[1]) != 3:
                # 1234,50 or 12,5 -> European decimal
                de_score += 5
            elif len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                # 1,000 or 1,234,567 -> English thousands
                en_score += 5
        elif "." in s and "," not in s:
            # e.g. 1234.50 vs 1.234
            parts = s.split(".")
            if len(parts) == 2 and len(parts[1]) != 3:
                en_score += 5
            elif len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                de_score += 5

    return "de_DE" if de_score > en_score else "en_US"


def parse_locale_number(val: Any, convention: str = "en_US") -> Decimal | None:
    """Parse single value into Decimal according to chosen locale convention."""
    if val is None:
        return None
    raw_str = str(val).strip()
    if not raw_str:
        return None

    cleaned, is_negative, is_percent = clean_currency_and_signs(raw_str)
    if not cleaned:
        return None

    if convention == "de_DE":
        # 1.234,50 -> remove dots, replace comma with dot
        normalized = cleaned.replace(" ", "").replace(".", "").replace(",", ".")
    else:
        # 1,234.50 -> remove commas and spaces
        normalized = cleaned.replace(" ", "").replace(",", "")

    try:
        dec = Decimal(normalized)
        if is_negative:
            dec = -dec
        if is_percent:
            dec = dec / Decimal(100)
        return dec
    except InvalidOperation:
        return None


def parse_numeric_column(
    col_name: str,
    values: list[Any],
) -> Tuple[list[Decimal | None], str, list[TransformationStep]]:
    """Parse entire column into Decimals and record parse_locale_number transformation."""
    str_samples = [str(v).strip() for v in values if v is not None and str(v).strip()]
    convention = infer_column_locale_convention(str_samples)

    parsed_values = [parse_locale_number(v, convention=convention) for v in values]

    transformations = [
        TransformationStep(
            id=generate_id("tr"),
            operation="parse_locale_number",
            parameters={"column": col_name, "convention": convention},
            rows_before=len(values),
            rows_after=len(values),
            requires_approval=False,
        )
    ]

    return parsed_values, convention, transformations
