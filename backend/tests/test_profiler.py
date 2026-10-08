"""Unit tests for dataset profiler, quality report builder, and PII masking."""

from pathlib import Path
import pandas as pd
import pytest

from backend.profile.pii import detect_column_pii, is_luhn_valid, is_solana_address, mask_sample
from backend.profile.profiler import profile_dataset
from backend.profile.quality import build_quality_report


def test_profiler_on_treasury_sample() -> None:
    csv_path = Path("fixtures/treasury_sample.csv")
    assert csv_path.exists()

    df = pd.read_csv(csv_path)
    profile = profile_dataset(df)

    assert profile["row_count"] == 1205
    assert profile["duplicate_rows"] == 5
    assert "wallet" in profile["constant_columns"] or "source" in profile["constant_columns"]

    # Check that columns are properly profiled
    col_names = [c["name"] for c in profile["columns"]]
    assert "amount_usd" in col_names
    assert "block_time" in col_names


def test_quality_report_builder() -> None:
    csv_path = Path("fixtures/treasury_sample.csv")
    df = pd.read_csv(csv_path)

    report = build_quality_report(df, dataset_name="treasury_sample")
    assert "issues" in report
    assert "stats" in report

    issue_details = " ".join(iss["detail"] for iss in report["issues"])
    # Must flag duplicate rows
    assert "duplicate" in issue_details.lower()
    # Must flag unpriced SOL rows
    assert "unpriced" in issue_details.lower()
    # Must flag failed transactions
    assert "failed" in issue_details.lower()


def test_pii_detection_rules() -> None:
    # 1. Solana public address is NOT PII
    sol_addr = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
    assert is_solana_address(sol_addr)
    level, _ = detect_column_pii("wallet", [sol_addr, sol_addr])
    assert level == "no"

    # 2. Email is PII
    emails = ["alice@example.com", "bob@crypto.org", "carol@analyx.xyz"]
    level, pii_type = detect_column_pii("user_email", emails)
    assert level == "yes"
    assert pii_type == "email"

    # 3. Phone is PII
    phones = ["+1 (555) 234-5678", "555-876-5432"]
    level, pii_type = detect_column_pii("contact_phone", phones)
    assert level == "yes"
    assert pii_type == "phone"

    # 4. Luhn credit card validation
    valid_card = "4532015112830366"  # Standard valid 16-digit test card number
    assert is_luhn_valid(valid_card)
    assert not is_luhn_valid("4532015112830367")  # Off by 1


def test_mask_sample_llm_safety() -> None:
    # Raw dataframe containing sensitive user information
    raw_df = pd.DataFrame({
        "customer_name": ["Alice Smith", "Bob Jones", "Alice Smith"],
        "email": ["alice@secret.org", "bob@private.io", "alice@secret.org"],
        "revenue": ["1500.00", "2200.00", "1500.00"],
    })

    masked = mask_sample(raw_df, max_rows=10)

    # Raw emails and names must not appear anywhere in masked dataframe
    for val in masked["email"]:
        assert "@" not in str(val)
        assert "EMAIL_" in str(val)

    for val in masked["customer_name"]:
        assert "Alice" not in str(val)
        assert "Bob" not in str(val)
        assert "NAME_" in str(val)

    # Identical values get stable tokens
    assert masked["customer_name"].iloc[0] == masked["customer_name"].iloc[2]
    assert masked["email"].iloc[0] == masked["email"].iloc[2]

    # Non-PII columns remain intact
    assert list(masked["revenue"]) == ["1500.00", "2200.00", "1500.00"]
