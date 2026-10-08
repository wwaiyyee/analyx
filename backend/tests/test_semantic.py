"""Unit tests for semantic dictionary proposal, crypto-aware rules, metric packs, and assumption ledger."""

from pathlib import Path
import pandas as pd
import pytest

from backend.semantic.assumptions import (
    ASSUMPTION_STABLECOIN_PARITY,
    AssumptionLedger,
)
from backend.semantic.dictionary import propose_dictionary
from backend.semantic.metrics import MetricPackRegistry


def test_dictionary_proposer_crypto_rules() -> None:
    df = pd.DataFrame({
        "tx_signature": ["5VERv8NM..."],
        "block_time": ["2026-08-01T12:00:00Z"],
        "wallet": ["7xKXtg2CW..."],
        "amount_usd": ["5000.00"],
        "amount_raw": ["5000000000"],
        "decimals": [6],
    })

    entries = propose_dictionary(df)
    role_map = {e["column"]: e["role"] for e in entries}

    # Core crypto roles
    assert role_map["tx_signature"] == "identifier"
    assert role_map["block_time"] == "date"
    assert role_map["wallet"] == "dimension"
    assert role_map["amount_usd"] == "measure"

    # Decimals rule: amount_raw MUST NEVER be assigned role='measure'
    assert role_map["amount_raw"] == "other"
    assert role_map["decimals"] == "other"


def test_treasury_metric_pack_loader() -> None:
    registry = MetricPackRegistry()
    pack_path = Path("metric_packs/treasury_v1.yaml")
    assert pack_path.exists()

    pack = registry.load_from_yaml(pack_path)
    assert pack.name == "treasury_v1"
    assert "inflow_usd" in pack.metrics
    assert "outflow_usd" in pack.metrics
    assert "net_flow_usd" in pack.metrics
    assert "tx_count" in pack.metrics
    assert "runway_months" in pack.metrics
    assert pack.metrics["runway_months"].is_derived is True

    # Column validation check
    available = ["direction", "amount_usd", "tx_status", "tx_signature", "counterparty"]
    missing = registry.validate_columns_for_metric("outflow_usd", available)
    assert missing == []

    # Missing column check
    missing_bad = registry.validate_columns_for_metric("outflow_usd", ["direction", "tx_status"])
    assert missing_bad == ["amount_usd"]


def test_generic_metric_pack_loader() -> None:
    registry = MetricPackRegistry()
    pack_path = Path("metric_packs/generic_v1.yaml")
    assert pack_path.exists()

    pack = registry.load_from_yaml(pack_path)
    assert pack.name == "generic_v1"
    assert "row_count" in pack.metrics
    assert "distinct_count" in pack.metrics
    assert "sum_amount" in pack.metrics


def test_assumption_ledger() -> None:
    ledger = AssumptionLedger()
    ses_id = "ses_test1"

    as1 = ledger.add(ses_id, ASSUMPTION_STABLECOIN_PARITY, source="system")
    assert as1.status == "active"
    assert as1.text == ASSUMPTION_STABLECOIN_PARITY

    # Associate with finding
    ledger.link_finding(as1.id, "fd_test_finding")
    fetched = ledger.get(as1.id)
    assert fetched is not None
    assert "fd_test_finding" in fetched.affects_finding_ids

    # Override
    ledger.override(as1.id)
    assert ledger.get(as1.id).status == "overridden"
