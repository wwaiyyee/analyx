"""Number-grounding linter verifying that all numeric tokens match Evidence metrics per §8.8 (1)."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re
from typing import Any


@dataclass
class NumberToken:
    raw: str
    value: Decimal
    tolerance: Decimal
    kind: str  # currency | percent | plain | multiplier


@dataclass
class NumberLintResult:
    passed: bool
    ungrounded_tokens: list[str] = field(default_factory=list)
    grounded_tokens: list[dict[str, Any]] = field(default_factory=list)


# Suffix multipliers
MULTIPLIERS = {
    "k": Decimal("1000"),
    "thousand": Decimal("1000"),
    "m": Decimal("1000000"),
    "million": Decimal("1000000"),
    "b": Decimal("1000000000"),
    "billion": Decimal("1000000000"),
    "t": Decimal("1000000000000"),
    "trillion": Decimal("1000000000000"),
}


def _clean_text_for_lint(text: str) -> str:
    """Strip code blocks, backticks, quotes, signatures, and dates that should not be linted."""
    # Strip markdown code blocks ``` ... ```
    cleaned = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    # Strip inline code ` ... `
    cleaned = re.sub(r"`.*?`", " ", cleaned)
    # Strip double quoted strings
    cleaned = re.sub(r'"[^"\n]*"', " ", cleaned)
    # Strip markdown links [label](url) -> keep label only
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    # Strip transaction signatures (base58 strings of length >= 32)
    cleaned = re.sub(r"\b[1-9A-HJ-NP-Za-km-z]{32,88}\b", " ", cleaned)
    # Strip date patterns (YYYY-MM-DD, YYYY/MM/DD, DD/MM/YYYY)
    cleaned = re.sub(r"\b\d{4}[-/]\d{2}[-/]\d{2}\b", " ", cleaned)
    cleaned = re.sub(r"\b\d{2}[-/]\d{2}[-/]\d{4}\b", " ", cleaned)
    # Strip month names with days and/or 4-digit years (e.g. August 1, 2026, August 1st, Aug 2026, 1 August 2026)
    _MONTHS = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    cleaned = re.sub(
        rf"\b{_MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTHS}(?:,?\s+\d{{4}})?\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b{_MONTHS}\s+\d{{4}}\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Strip isolated 4-digit years in date contexts (e.g. 'in 2026', 'for 2025', 'FY2026')
    cleaned = re.sub(r"\b(?:in|of|for|since|during|FY|year)\s+(20\d\d|19\d\d)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(20\d\d|19\d\d)\b", " ", cleaned)
    # Strip Quarters (Q1, Q2, Q3, Q4)
    cleaned = re.sub(r"\bQ[1-4]\b", " ", cleaned, flags=re.IGNORECASE)
    # Strip numbered list markers at line start or sentence start (e.g. '1. ', '2) ')
    cleaned = re.sub(r"(?:^|\n|\.\s+)\d+[\.\)]\s+", " ", cleaned)
    # Strip ordinals (1st, 2nd, 3rd, 4th, etc.)
    cleaned = re.sub(r"\b\d+(?:st|nd|rd|th)\b", " ", cleaned, flags=re.IGNORECASE)

    return cleaned


def extract_numeric_tokens(text: str) -> list[NumberToken]:
    """Parse text and extract all quantitative values with associated rounding tolerance."""
    cleaned = _clean_text_for_lint(text)
    tokens: list[NumberToken] = []

    # Pattern for numeric expressions:
    # 1. Currency/numbers with suffixes: $1.2M, $500k, 1.5 million, 45.2%
    # Regex captures:
    # (prefix $, +, -)? (\d+(?:,\d{3})*(?:\.\d+)?) (\s*(?:k|m|b|t|thousand|million|billion|trillion|%))?
    pattern = re.compile(
        r"(?P<prefix>[\$€£\+\-])?\s*(?P<num>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<suffix>%|k|m|b|t|thousand|million|billion|trillion)?(?!\w)",
        re.IGNORECASE,
    )

    for m in pattern.finditer(cleaned):
        raw_match = m.group(0).strip()
        num_str = m.group("num").replace(",", "")
        prefix = m.group("prefix") or ""
        suffix = (m.group("suffix") or "").lower()

        try:
            base_val = Decimal(num_str)
        except InvalidOperation:
            continue

        if "-" in prefix:
            base_val = -base_val

        # Decimal precision in string
        dec_places = len(num_str.split(".")[1]) if "." in num_str else 0

        if suffix in MULTIPLIERS:
            mult = MULTIPLIERS[suffix]
            val = base_val * mult
            # e.g., 1.2M -> step is 0.1 * 1,000,000 = 100,000; tolerance is half step = 50,000
            step = (Decimal("10") ** -dec_places) * mult
            tol = step / Decimal("2")
            tokens.append(NumberToken(raw=raw_match, value=val, tolerance=tol, kind="multiplier"))

        elif suffix == "%":
            # e.g., 14.8% -> step is 0.1 percentage points; tolerance is 0.05
            step = Decimal("10") ** -dec_places
            tol = step / Decimal("2")
            tokens.append(NumberToken(raw=raw_match, value=base_val, tolerance=tol, kind="percent"))

        elif prefix in ("$", "€", "£"):
            step = Decimal("10") ** -dec_places if dec_places > 0 else Decimal("1")
            tol = step / Decimal("2")
            tokens.append(NumberToken(raw=raw_match, value=base_val, tolerance=tol, kind="currency"))

        else:
            step = Decimal("10") ** -dec_places if dec_places > 0 else Decimal("0.5")
            tol = step / Decimal("2") if dec_places > 0 else Decimal("0")
            tokens.append(NumberToken(raw=raw_match, value=base_val, tolerance=tol, kind="plain"))

    return tokens


def _collect_evidence_values(metrics: dict[str, Any]) -> list[tuple[str, Decimal]]:
    """Extract all scalar numeric values from metrics dict."""
    evidence_nums: list[tuple[str, Decimal]] = []
    for k, v in metrics.items():
        if v is None:
            continue
        try:
            # Handle string or numeric representation
            s_val = str(v).replace(",", "").replace("$", "").replace("%", "").strip()
            dec_val = Decimal(s_val)
            evidence_nums.append((k, dec_val))
        except (InvalidOperation, ValueError):
            continue
    return evidence_nums


def lint_numbers(text: str, evidence_metrics: dict[str, Any]) -> NumberLintResult:
    """Verify that all quantitative tokens in text match evidence metrics within rounding precision.

    Returns NumberLintResult with passed status and any ungrounded tokens.
    """
    tokens = extract_numeric_tokens(text)
    if not tokens:
        return NumberLintResult(passed=True)

    ev_values = _collect_evidence_values(evidence_metrics)
    if not ev_values:
        # Text has numbers but evidence has none -> fail
        return NumberLintResult(
            passed=False,
            ungrounded_tokens=[t.raw for t in tokens],
        )

    ungrounded: list[str] = []
    grounded: list[dict[str, Any]] = []

    for tok in tokens:
        matched = False
        for metric_name, ev_val in ev_values:
            # Match direct value with tolerance
            diff = abs(tok.value - ev_val)
            if diff <= tok.tolerance:
                matched = True
                grounded.append({"token": tok.raw, "metric": metric_name, "expected": str(ev_val)})
                break

            # If percentage, check ratio form (e.g. 14.8% vs 0.148)
            if tok.kind == "percent":
                ratio_val = tok.value / Decimal("100")
                if abs(ratio_val - ev_val) <= (tok.tolerance / Decimal("100")):
                    matched = True
                    grounded.append({"token": tok.raw, "metric": metric_name, "expected": str(ev_val)})
                    break
                # Also check 0.148 vs 14.8
                mult_val = ev_val * Decimal("100")
                if abs(tok.value - mult_val) <= tok.tolerance:
                    matched = True
                    grounded.append({"token": tok.raw, "metric": metric_name, "expected": str(ev_val)})
                    break

        if not matched:
            ungrounded.append(tok.raw)

    return NumberLintResult(
        passed=len(ungrounded) == 0,
        ungrounded_tokens=ungrounded,
        grounded_tokens=grounded,
    )
