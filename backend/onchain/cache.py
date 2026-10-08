"""On-chain raw batch and normalized Parquet caching per §8.3."""

import json
from pathlib import Path
from typing import Tuple
import pandas as pd

from backend.config import settings
from backend.core.hashing import canonical_table_hash
from backend.onchain.source import RawTxBatch


def get_cache_key(address: str, cluster: str, from_slot: int | None, to_slot: int | None) -> str:
    """Generate standardized cache key for on-chain dataset."""
    f_slot = from_slot if from_slot is not None else 0
    t_slot = to_slot if to_slot is not None else 0
    return f"{address[:12]}_{cluster}_{f_slot}_{t_slot}"


def cache_onchain_dataset(
    batch: RawTxBatch,
    df: pd.DataFrame,
    data_dir: Path | str | None = None,
) -> Tuple[str, str, str]:
    """Persist raw transaction batch JSON and normalized Parquet table to disk.

    Returns: (raw_json_path, parquet_path, canonical_content_hash)
    """
    out_dir = Path(data_dir or settings.data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    key = get_cache_key(batch.address, batch.cluster, batch.from_slot, batch.to_slot)
    raw_path = str(out_dir / f"onchain_{key}_raw.json")
    parquet_path = str(out_dir / f"onchain_{key}.parquet")

    # 1. Save raw batch JSON
    raw_meta = {
        "address": batch.address,
        "cluster": batch.cluster,
        "from_slot": batch.from_slot,
        "to_slot": batch.to_slot,
        "complete_history": batch.complete_history,
        "fetched_at": batch.fetched_at,
        "source": batch.source,
        "tx_count": len(batch.transactions),
    }
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({"meta": raw_meta, "transactions": batch.transactions}, f)

    # 2. Compute canonical table hash
    c_hash = canonical_table_hash(df)

    # 3. Save normalized DataFrame to Parquet
    df_parquet = df.copy()
    if "block_time" in df_parquet.columns:
        df_parquet["block_time"] = pd.to_datetime(df_parquet["block_time"], utc=True)
    df_parquet.to_parquet(parquet_path, engine="pyarrow", index=False)

    return raw_path, parquet_path, c_hash


def get_cached_onchain(
    address: str,
    cluster: str = "devnet",
    data_dir: Path | str | None = None,
) -> Tuple[pd.DataFrame, str] | None:
    """Check disk cache for existing normalized onchain dataset for address."""
    out_dir = Path(data_dir or settings.data_dir)
    pattern = f"onchain_{address[:12]}_{cluster}_*.parquet"
    matches = list(out_dir.glob(pattern))
    if not matches:
        return None

    # Load latest modified parquet
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    target = matches[0]
    df = pd.read_parquet(target)
    c_hash = canonical_table_hash(df)
    return df, c_hash
