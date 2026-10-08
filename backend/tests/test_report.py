"""Unit tests for report generator and frozen-region hashing stability per §8.10."""

import hashlib
from backend.report.generator import generate_report_markdown


def test_report_generation_and_hash_stability() -> None:
    datasets = [
        {
            "name": "Treasury Transactions",
            "kind": "csv",
            "row_count": 1205,
            "content_hash": "1dd45436179eb61dd796b42b101fa2ff07b22a001859be6ba5e378d3807d9f78",
            "time_anchor": "2026-08-31T23:59:59Z",
        }
    ]

    findings = [
        {
            "claim": "August outflow reached $125,000.00",
            "claim_type": "metric",
            "status": "supported",
            "evidence_id": "ev_01test123",
        }
    ]

    evidence_map = {
        "ev_01test123": {
            "metrics": {
                "outflow_usd": "$125,000.00",
                "tx_count": 42,
            }
        }
    }

    assumptions = [
        {"text": "August 2026 calendar month considered complete", "status": "active"}
    ]

    # Generate initial unanchored report
    frozen_1, sha_1, complete_1 = generate_report_markdown(
        title="Treasury Financial Report",
        session_id="ses_test123",
        datasets=datasets,
        findings=findings,
        evidence_map=evidence_map,
        assumptions=assumptions,
    )

    # 1. Verify all 9 sections exist in frozen content
    for sec_num in range(1, 10):
        assert f"## {sec_num}." in frozen_1

    # 2. Verify sha256 matches exact hash of frozen body
    expected_sha = hashlib.sha256(frozen_1.encode("utf-8")).hexdigest()
    assert sha_1 == expected_sha

    # 3. Simulate post-attestation appending of Section 10
    attestation_info = {
        "root": "a1b2c3d4e5f60000000000000000000000000000000000000000000000000000",
        "signer": "7Mm2sT4b5oXoEHQrK5D3z189G7p4YvV8WkPq6s5L3r12",
        "cluster": "devnet",
        "tx_signature": "5Kj8...solana_tx_signature",
        "block_time": "2026-10-08T12:00:00Z",
    }

    frozen_2, sha_2, complete_2 = generate_report_markdown(
        title="Treasury Financial Report",
        session_id="ses_test123",
        datasets=datasets,
        findings=findings,
        evidence_map=evidence_map,
        assumptions=assumptions,
        attestation_info=attestation_info,
    )

    # 4. Critical invariant: Frozen body and report hash MUST remain 100% IDENTICAL before and after attestation
    assert frozen_1 == frozen_2
    assert sha_1 == sha_2

    # Section 10 is present ONLY in complete_2
    assert "## 10. Verification & On-Chain Anchor" not in frozen_2
    assert "## 10. Verification & On-Chain Anchor" in complete_2
    assert attestation_info["root"] in complete_2
