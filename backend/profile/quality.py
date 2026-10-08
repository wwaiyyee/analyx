"""Quality report builder per §8.2: diagnostic issues, severity grading, and metric impacts."""

from typing import Any
import pandas as pd

from backend.core.ids import generate_id
from backend.profile.profiler import profile_dataset


def build_quality_report(df: pd.DataFrame, dataset_name: str = "dataset") -> dict[str, Any]:
    """Analyze DataFrame and generate structured quality report with diagnostics and stats."""
    stats = profile_dataset(df)
    issues: list[dict[str, Any]] = []

    # 1. Duplicate rows
    if stats["duplicate_rows"] > 0:
        issues.append({
            "id": generate_id("iss"),
            "severity": "warn",
            "columns": list(df.columns),
            "detail": f"Dataset contains {stats['duplicate_rows']} duplicate row(s). Duplicates are flagged but never deleted without approval.",
            "affects_metrics": ["row_count", "tx_count"],
        })

    # 2. Constant columns
    if stats["constant_columns"]:
        issues.append({
            "id": generate_id("iss"),
            "severity": "info",
            "columns": stats["constant_columns"],
            "detail": f"Column(s) {stats['constant_columns']} have constant or single distinct values.",
            "affects_metrics": [],
        })

    # 3. High null percentages & outliers per column
    for col_info in stats["columns"]:
        c_name = col_info["name"]
        null_count = col_info["null_count"]
        null_pct_float = float(col_info["null_pct"])

        if null_pct_float >= 50.0:
            issues.append({
                "id": generate_id("iss"),
                "severity": "high",
                "columns": [c_name],
                "detail": f"Column '{c_name}' has high missingness ({null_pct_float}% nulls, {null_count} rows).",
                "affects_metrics": [c_name],
            })
        elif null_pct_float >= 10.0:
            issues.append({
                "id": generate_id("iss"),
                "severity": "warn",
                "columns": [c_name],
                "detail": f"Column '{c_name}' contains {null_pct_float}% null values ({null_count} rows).",
                "affects_metrics": [c_name],
            })

        # Outliers
        if col_info.get("outlier_count", 0) > 0:
            issues.append({
                "id": generate_id("iss"),
                "severity": "info",
                "columns": [c_name],
                "detail": f"Column '{c_name}' has {col_info['outlier_count']} statistical outlier(s) based on the 1.5*IQR rule.",
                "affects_metrics": [c_name],
            })

    # 4. Check unpriced tokens (SOL without price_usd) in crypto schemas
    if "token_symbol" in df.columns and "price_usd" in df.columns:
        unpriced = df[(df["token_symbol"] == "SOL") & (df["price_usd"].isna())]
        if not unpriced.empty:
            issues.append({
                "id": generate_id("iss"),
                "severity": "warn",
                "columns": ["token_symbol", "price_usd"],
                "detail": f"Found {len(unpriced)} unpriced SOL transaction(s) with null USD price. Excluded from USD metrics.",
                "affects_metrics": ["outflow_usd", "inflow_usd", "net_flow_usd"],
            })

    # 5. Check failed transactions
    if "tx_status" in df.columns:
        failed_count = int((df["tx_status"] == "failed").sum())
        if failed_count > 0:
            issues.append({
                "id": generate_id("iss"),
                "severity": "info",
                "columns": ["tx_status"],
                "detail": f"Dataset contains {failed_count} failed transaction(s). Excluded from financial metrics by default.",
                "affects_metrics": ["outflow_usd", "inflow_usd", "tx_count"],
            })

    return {
        "dataset_name": dataset_name,
        "issues": issues,
        "stats": stats,
    }
