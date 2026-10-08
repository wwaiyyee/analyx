"""Data dictionary proposer with crypto-aware heuristics per §8.3 (A3).

Assigns semantic roles: 'date', 'measure', 'dimension', 'identifier', 'other'.
Enforces the decimals rule: raw token amounts (amount_raw) are assigned 'other', never 'measure'.
"""

from typing import Any, Literal
import pandas as pd

from backend.profile.pii import detect_column_pii

ColumnRole = Literal["date", "measure", "dimension", "identifier", "other"]

CRYPTO_ROLES: dict[str, dict[str, Any]] = {
    "tx_signature": {"role": "identifier", "unit": None, "desc": "Unique Solana transaction signature"},
    "slot": {"role": "identifier", "unit": None, "desc": "Solana ledger block slot number"},
    "block_time": {"role": "date", "unit": "UTC", "desc": "Transaction block timestamp in UTC"},
    "wallet": {"role": "dimension", "unit": None, "desc": "Analyzed wallet public key"},
    "counterparty": {"role": "dimension", "unit": None, "desc": "Counterparty account address"},
    "counterparty_confidence": {"role": "dimension", "unit": None, "desc": "Confidence of counterparty attribution"},
    "direction": {"role": "dimension", "unit": None, "desc": "Direction of balance change (in or out)"},
    "token_mint": {"role": "dimension", "unit": None, "desc": "SPL token mint public address"},
    "token_symbol": {"role": "dimension", "unit": None, "desc": "Normalized token ticker symbol"},
    "decimals": {"role": "other", "unit": "count", "desc": "Token decimal places"},
    "amount_raw": {"role": "other", "unit": None, "desc": "Raw unscaled base token units (Decimals rule: not a measure)"},
    "amount": {"role": "measure", "unit": "tokens", "desc": "Normalized absolute token amount"},
    "price_usd": {"role": "measure", "unit": "USD", "desc": "Price per token in USD at transaction time"},
    "amount_usd": {"role": "measure", "unit": "USD", "desc": "Total value transferred in USD"},
    "fee_lamports": {"role": "measure", "unit": "lamports", "desc": "Transaction fee paid by wallet"},
    "tx_status": {"role": "dimension", "unit": None, "desc": "Transaction execution status (success or failed)"},
    "source": {"role": "dimension", "unit": None, "desc": "Data ingestion provenance source"},
}


def propose_column_role(col_name: str, series: pd.Series) -> tuple[ColumnRole, str | None, str]:
    """Determine role, unit, and description for a column using crypto heuristics, dtype, and cardinality."""
    lower_name = col_name.lower().replace("-", "_")

    # 1. Exact match in fixed crypto schema
    if lower_name in CRYPTO_ROLES:
        info = CRYPTO_ROLES[lower_name]
        return info["role"], info["unit"], info["desc"]

    # 2. Identifier heuristics
    if any(k in lower_name for k in ("signature", "_id", "id", "uuid", "guid", "hash", "pk", "key")):
        return "identifier", None, f"Identifier column '{col_name}'"

    # 3. Date heuristics
    if pd.api.types.is_datetime64_any_dtype(series) or any(k in lower_name for k in ("date", "time", "timestamp", "day", "month", "year", "created")):
        return "date", "UTC" if "time" in lower_name else None, f"Temporal column '{col_name}'"

    # 4. Decimals rule guard: never treat amount_raw as measure
    if "raw" in lower_name and any(k in lower_name for k in ("amount", "balance", "unit")):
        return "other", None, f"Raw unscaled integer '{col_name}' (Decimals rule applies)"

    # 5. Measure / metric heuristics
    if pd.api.types.is_numeric_dtype(series) or any(k in lower_name for k in ("amount", "usd", "price", "revenue", "cost", "fee", "vol", "units", "count", "rate")):
        unit = "USD" if any(k in lower_name for k in ("usd", "dollar", "price", "revenue", "cost")) else None
        return "measure", unit, f"Quantitative metric '{col_name}'"

    # 6. Default to dimension for categorical/text columns
    return "dimension", None, f"Categorical attribute '{col_name}'"


def propose_dictionary(df: pd.DataFrame, dataset_version_id: str = "") -> list[dict[str, Any]]:
    """Propose initial data dictionary entries for all columns in DataFrame."""
    entries: list[dict[str, Any]] = []

    for col in df.columns:
        series = df[col]
        role, unit, desc = propose_column_role(col, series)
        pii_level, _ = detect_column_pii(col, series.tolist())

        entries.append({
            "dataset_version_id": dataset_version_id,
            "column": col,
            "role": role,
            "unit": unit,
            "description": desc,
            "pii": pii_level,
            "confirmed_by_user": False,
        })

    return entries
