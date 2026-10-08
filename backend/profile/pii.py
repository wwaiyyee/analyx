"""PII detector and sample masking per §8.2 (T11).

Rules:
- Emails, phone numbers, names, SSNs, and Luhn credit cards are flagged as PII.
- Solana-looking base58 strings (32-44 chars) are public addresses: marked pii='no' but role='identifier'.
- mask_sample(df) replaces PII values with stable tokens (e.g. EMAIL_1, NAME_2) for LLM exposure.
"""

import re
from typing import Any, Literal, Tuple
import pandas as pd

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_RE = re.compile(r"^(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$")
SSN_RE = re.compile(r"^\d{3}-\d{2}-\d{4}$")
SOLANA_B58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

PIILevel = Literal["no", "maybe", "yes"]


def is_luhn_valid(number_str: str) -> bool:
    """Verify standard Luhn mod-10 algorithm for credit card numbers."""
    digits = [int(c) for c in number_str if c.isdigit()]
    if len(digits) not in range(13, 20):
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def is_solana_address(val: str) -> bool:
    """Check if value is a valid Solana public address (32-44 base58 chars)."""
    s = val.strip()
    return bool(SOLANA_B58_RE.match(s))


def detect_column_pii(col_name: str, values: list[Any]) -> Tuple[PIILevel, str | None]:
    """Classify column PII status as 'no', 'maybe', or 'yes' along with detected category."""
    lower_name = col_name.lower().replace("_", "").replace("-", "")

    # Exclude on-chain public addresses
    if any(k in lower_name for k in ("wallet", "signature", "txsignature", "mint", "programid")):
        return "no", None

    non_empty = [str(v).strip() for v in values if v is not None and str(v).strip()]
    if not non_empty:
        return "no", None

    # Check if column is predominantly Solana base58 addresses
    solana_matches = sum(1 for s in non_empty[:50] if is_solana_address(s))
    if solana_matches / min(50, len(non_empty)) >= 0.7:
        return "no", None

    # 1. Email check
    if "email" in lower_name or sum(1 for s in non_empty[:30] if EMAIL_RE.match(s)) >= 2:
        return "yes", "email"

    # 2. Phone check
    if any(k in lower_name for k in ("phone", "tel", "mobile")) or sum(
        1 for s in non_empty[:30] if PHONE_RE.match(s)
    ) >= 2:
        return "yes", "phone"

    # 3. SSN check
    if "ssn" in lower_name or sum(1 for s in non_empty[:30] if SSN_RE.match(s)) >= 2:
        return "yes", "ssn"

    # 4. Credit card Luhn check
    luhn_matches = sum(
        1 for s in non_empty[:30]
        if s.replace(" ", "").replace("-", "").isdigit() and is_luhn_valid(s)
    )
    if luhn_matches >= 1:
        return "yes", "credit_card"

    # 5. Name check
    if any(k in lower_name for k in ("fullname", "firstname", "lastname", "customername", "username")):
        return "yes", "name"
    if lower_name in ("name", "customer", "user", "contact"):
        return "maybe", "name"

    return "no", None


def mask_sample(
    df: pd.DataFrame,
    max_rows: int = 20,
    pii_map: dict[str, PIILevel] | None = None,
) -> pd.DataFrame:
    """Produce a safe sample of <= 20 rows where any PII columns are masked with stable tokens."""
    sample_df = df.head(max_rows).copy()

    # Determine PII columns if not explicitly provided
    if pii_map is None:
        pii_map = {}
        for col in df.columns:
            level, _ = detect_column_pii(col, df[col].tolist())
            pii_map[col] = level

    # Stable token maps per column
    for col, level in pii_map.items():
        if level in ("yes", "maybe") and col in sample_df.columns:
            token_cache: dict[str, str] = {}
            masked_values = []
            prefix = "NAME" if "name" in col.lower() else ("EMAIL" if "email" in col.lower() else "PII")

            for val in sample_df[col]:
                if pd.isna(val) or val is None or str(val).strip() == "":
                    masked_values.append(val)
                else:
                    raw_str = str(val).strip()
                    if raw_str not in token_cache:
                        token_cache[raw_str] = f"{prefix}_{len(token_cache) + 1}"
                    masked_values.append(token_cache[raw_str])

            sample_df[col] = masked_values

    return sample_df
