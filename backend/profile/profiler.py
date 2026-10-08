"""Dataset profiler calculating per-column statistics and dataset-level diagnostics per §8.2."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Tuple
import pandas as pd


def _is_numeric_series(series: pd.Series) -> bool:
    """Check if pandas series contains numeric values."""
    if pd.api.types.is_numeric_dtype(series):
        return True
    # Try converting non-null values
    non_null = series.dropna().astype(str).tolist()[:50]
    if not non_null:
        return False
    digits = sum(
        1 for s in non_null
        if s.replace(".", "", 1).replace("-", "", 1).replace(",", "", 1).isdigit()
    )
    return digits / len(non_null) >= 0.8


def _is_datetime_series(series: pd.Series) -> bool:
    """Check if pandas series contains date or datetime values."""
    return pd.api.types.is_datetime64_any_dtype(series)


def profile_column(col_name: str, series: pd.Series) -> dict[str, Any]:
    """Calculate thorough per-column statistics for a single column."""
    total_count = len(series)
    null_count = int(series.isna().sum())
    null_pct = f"{(null_count / total_count * 100):.2f}" if total_count > 0 else "0.00"
    valid_series = series.dropna()

    distinct_count = int(valid_series.nunique())

    profile: dict[str, Any] = {
        "name": col_name,
        "total_count": total_count,
        "null_count": null_count,
        "null_pct": null_pct,
        "distinct_count": distinct_count,
    }

    if _is_numeric_series(valid_series) and not valid_series.empty:
        nums = pd.to_numeric(valid_series, errors="coerce").dropna()
        if not nums.empty:
            profile["dtype"] = "numeric"
            profile["min"] = f"{nums.min():.2f}"
            profile["max"] = f"{nums.max():.2f}"
            profile["mean"] = f"{nums.mean():.2f}"
            profile["median"] = f"{nums.median():.2f}"

            # IQR outlier check
            q25 = nums.quantile(0.25)
            q75 = nums.quantile(0.75)
            iqr = q75 - q25
            lower_bound = q25 - 1.5 * iqr
            upper_bound = q75 + 1.5 * iqr
            outliers = nums[(nums < lower_bound) | (nums > upper_bound)]
            profile["outlier_count"] = int(len(outliers))
            profile["outlier_bounds"] = {
                "lower": f"{lower_bound:.2f}",
                "upper": f"{upper_bound:.2f}",
            }
            return profile

    if _is_datetime_series(valid_series) and not valid_series.empty:
        dt_series = pd.to_datetime(valid_series, errors="coerce", utc=True).dropna()
        if not dt_series.empty:
            profile["dtype"] = "datetime"
            profile["min_date"] = dt_series.min().isoformat()
            profile["max_date"] = dt_series.max().isoformat()
            profile["date_span_days"] = (dt_series.max() - dt_series.min()).days
            return profile

    # Categorical or string series
    profile["dtype"] = "string"
    value_counts = valid_series.astype(str).value_counts().head(10)
    profile["top_10"] = [
        {"value": str(val), "count": int(cnt)}
        for val, cnt in value_counts.items()
    ]
    if not valid_series.empty:
        profile["sample"] = [str(x) for x in valid_series.iloc[:5].tolist()]

    return profile


def profile_dataset(df: pd.DataFrame) -> dict[str, Any]:
    """Calculate comprehensive dataset-level profile including duplicate and constant rows."""
    row_count = len(df)
    col_count = len(df.columns)

    # Duplicate rows
    duplicate_count = int(df.duplicated().sum())

    # Constant columns
    constant_columns = [
        col for col in df.columns if df[col].nunique(dropna=False) <= 1
    ]

    # Per-column profiles
    col_profiles: list[dict[str, Any]] = []
    for col in df.columns:
        col_profiles.append(profile_column(col, df[col]))

    return {
        "row_count": row_count,
        "col_count": col_count,
        "duplicate_rows": duplicate_count,
        "constant_columns": constant_columns,
        "columns": col_profiles,
    }
