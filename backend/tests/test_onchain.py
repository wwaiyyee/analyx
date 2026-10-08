"""Unit tests for Solana on-chain source, offline mode, normalization, and caching."""

import asyncio
from pathlib import Path
import tempfile
import pandas as pd
import pytest

from backend.onchain.cache import cache_onchain_dataset, get_cached_onchain
from backend.onchain.normalize_transfers import normalize_raw_batch
from backend.onchain.rpc_source import RpcSource


def test_offline_mode_loads_fixture() -> None:
    wallet = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
    source = RpcSource(offline_mode=True)
    batch = asyncio.run(source.fetch(wallet, cluster="devnet"))

    assert batch.source == "fixture"
    assert batch.address == wallet
    assert len(batch.transactions) >= 5
    assert batch.complete_history is True


def test_normalize_raw_batch_transfers() -> None:
    wallet = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
    source = RpcSource(offline_mode=True)
    batch = source._load_offline_fixture(wallet, "devnet")

    df = normalize_raw_batch(batch)
    assert not df.empty

    # 1. Verify SPL USDC transfer
    usdc_rows = df[df["token_symbol"] == "USDC"]
    assert len(usdc_rows) >= 1
    usdc_row = usdc_rows.iloc[0]
    assert usdc_row["direction"] == "out"
    assert usdc_row["price_usd"] == "1.00"
    assert usdc_row["amount_usd"] == "5000.00"
    assert usdc_row["counterparty"] == "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
    assert usdc_row["counterparty_confidence"] == "high"

    # 2. Verify SPL USDT transfer (inbound)
    usdt_rows = df[df["token_symbol"] == "USDT"]
    assert len(usdt_rows) >= 1
    usdt_row = usdt_rows.iloc[0]
    assert usdt_row["direction"] == "in"
    assert usdt_row["amount"] == "12500"
    assert usdt_row["price_usd"] == "1.00"

    # 3. Verify SOL native transfer
    sol_rows = df[(df["token_symbol"] == "SOL") & (df["tx_status"] == "success")]
    assert len(sol_rows) >= 1
    sol_row = sol_rows.iloc[0]
    assert sol_row["direction"] == "out"
    assert sol_row["amount"] == "2.5"
    assert pd.isna(sol_row["price_usd"])

    # 4. Verify failed transaction is preserved
    failed_rows = df[df["tx_status"] == "failed"]
    assert len(failed_rows) >= 1
    assert failed_rows.iloc[0]["fee_lamports"] > 0


def test_onchain_caching() -> None:
    wallet = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
    source = RpcSource(offline_mode=True)
    batch = source._load_offline_fixture(wallet, "devnet")
    df = normalize_raw_batch(batch)

    with tempfile.TemporaryDirectory() as tmp_dir:
        raw_p, parquet_p, c_hash = cache_onchain_dataset(batch, df, data_dir=tmp_dir)

        assert Path(raw_p).exists()
        assert Path(parquet_p).exists()
        assert len(c_hash) == 64

        cached = get_cached_onchain(wallet, "devnet", data_dir=tmp_dir)
        assert cached is not None
        cached_df, cached_hash = cached
        assert len(cached_df) == len(df)
        assert cached_hash == c_hash
