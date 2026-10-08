"""Tests for TEE Confidential Execution Backend and hardware quote verification."""

from backend.backends.tee import TeeBackend
from backend.config import settings


def test_tee_measurement_reproducibility() -> None:
    tee = TeeBackend()
    measurement = tee.get_measurement()
    assert len(measurement) == 64
    assert measurement == tee.get_measurement()


def test_tee_generate_and_verify_quote() -> None:
    tee = TeeBackend()
    report_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    quote = tee.generate_enclave_quote(report_sha)

    assert quote["provider"] == "confidential-enclave-sevsnp"
    assert quote["verified"] is True
    assert quote["report_data"] == report_sha
    assert len(quote["quote_signature"]) == 64

    # Verify quote
    assert tee.verify_enclave_quote(quote, expected_report_data=report_sha) is True

    # Tampered report data must fail verification
    assert tee.verify_enclave_quote(quote, expected_report_data="tampered_hash") is False


def test_tee_execute_query(tmp_path) -> None:
    import pandas as pd
    tee = TeeBackend()

    # Create dummy parquet
    df = pd.DataFrame({"id": [1, 2, 3], "amount": [10.5, 20.0, 30.5]})
    p_path = str(tmp_path / "test.parquet")
    df.to_parquet(p_path)

    res = tee.execute_query("SELECT SUM(amount) as total FROM t", [], {"t": p_path})
    assert res.row_count == 1
    assert res.columns == ["total"]
    assert res.rows[0][0] == "61.00"
