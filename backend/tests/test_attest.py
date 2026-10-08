"""Unit and integration test suite for security sanitization and Solana attestation."""

import pytest

from backend.attest.bundle import build_attestation_bundle
from backend.attest.models import DatasetRef, EvidenceRef
from backend.attest.root import compute_attestation_root, format_solana_memo, parse_memo_root
from backend.attest.solana_verify import verify_onchain_memo
from backend.core.errors import ValidationError
from backend.security.sanitize import (
    MAX_FILE_SIZE_BYTES,
    sanitize_csv_cell,
    validate_file_upload,
)


# --- 1. Security & Sanitization Tests ---

def test_file_upload_validation() -> None:
    # Valid CSV
    validate_file_upload("valid_data.csv", b"col1,col2\n1,2")

    # Invalid extension
    with pytest.raises(ValidationError):
        validate_file_upload("script.exe", b"binary content")

    # Oversized file
    oversized = b"0" * (MAX_FILE_SIZE_BYTES + 1024)
    with pytest.raises(ValidationError):
        validate_file_upload("large.csv", oversized)


def test_csv_formula_injection_defense() -> None:
    # Malicious formula strings neutralized with leading quote
    assert sanitize_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("@SUM(1+1)") == "'@SUM(1+1)"

    # Normal negative number preserved without prepending quote
    assert sanitize_csv_cell("-123.45") == "-123.45"
    assert sanitize_csv_cell("-1000") == "-1000"

    # Plain text / numbers unchanged
    assert sanitize_csv_cell("Normal Text") == "Normal Text"
    assert sanitize_csv_cell(42) == 42


# --- 2. Attestation Bundle & Root Determinism ---

def test_attestation_bundle_construction_and_root() -> None:
    datasets = [
        DatasetRef(id="ds_1", version_hash="aaaa" * 16, kind="csv"),
        DatasetRef(id="ds_1_dup", version_hash="aaaa" * 16, kind="csv"),  # Duplicate hash
        DatasetRef(id="ds_2", version_hash="bbbb" * 16, kind="onchain"),
    ]
    evidence = [
        EvidenceRef(id="ev_1", sha256="1111" * 16),
        EvidenceRef(id="ev_1_dup", sha256="1111" * 16),
        EvidenceRef(id="ev_2", sha256="2222" * 16),
    ]

    bundle = build_attestation_bundle(
        report_id="rp_test1",
        report_sha256="3333" * 16,
        datasets=datasets,
        evidence=evidence,
        signer="7Mm2sT4b5oXoEHQrK5D3z189G7p4YvV8WkPq6s5L3r12",
        created_at="2026-08-31T23:59:59Z",
    )

    # Verify deduplication
    assert len(bundle.datasets) == 2
    assert len(bundle.evidence) == 2

    # Verify root hash determinism
    root_1 = compute_attestation_root(bundle)
    root_2 = compute_attestation_root(bundle)
    assert root_1 == root_2
    assert len(root_1) == 64

    # Memo formatting and parsing
    memo = format_solana_memo(root_1)
    assert memo == f"analyx:v1:{root_1}"
    assert parse_memo_root(memo) == root_1
    assert parse_memo_root("invalid:prefix:123") is None


# --- 3. On-chain Verification Logic ---

def test_verify_onchain_memo_mock() -> None:
    root = "a" * 64
    signer = "7Mm2sT4b5oXoEHQrK5D3z189G7p4YvV8WkPq6s5L3r12"

    res = verify_onchain_memo(
        tx_signature="mock_tx_signature_123",
        expected_root=root,
        expected_signer=signer,
    )
    assert res.success
    assert res.status == "confirmed"
