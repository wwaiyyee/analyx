"""Unit and integration test suites for validators: number lint, language lint, invariants, and recompute."""

from decimal import Decimal
from pathlib import Path
import pytest

from backend.backends.local import LocalBackend
from backend.core.hashing import hash_obj
from backend.engine.compile import compile_spec
from backend.engine.models import AnalysisSpec, MetricRef, TimeWindow
from backend.ingest.normalize import normalize_dataset
from backend.semantic.metrics import load_metric_pack
from backend.validate.evidence_status import (
    check_percentage_invariant,
    check_segment_sum_invariant,
    evaluate_evidence_status,
)
from backend.validate.language_lint import lint_language
from backend.validate.number_lint import lint_numbers
from backend.validate.recompute import recompute_spec


# --- 1. Number Grounding Lint Tests ---

def test_number_lint_exact_and_tolerance_match() -> None:
    metrics = {
        "outflow_usd": "1234.50",
        "tx_count": 42,
        "large_sum": "1210000.00",
        "ratio": "0.1481",
    }

    # Positive: exact currency, plain number, 1.2M within tolerance, percentage within tolerance
    text = (
        "In August 2026, we processed 42 transactions totaling $1,234.50. "
        "Overall capital totaled $1.2M, representing 14.8% of assets."
    )
    res = lint_numbers(text, metrics)
    assert res.passed
    assert len(res.ungrounded_tokens) == 0


def test_number_lint_ignores_dates_and_ordinals() -> None:
    metrics = {"volume": "5000"}
    # 2026, Q3, 1st, 2nd, August 1, 2026, `col_name` should all be ignored
    text = (
        "As of August 1, 2026, during Q3 in 2026, the 1st and 2nd batches of `run_id_99` "
        "reached 5,000 units."
    )
    res = lint_numbers(text, metrics)
    assert res.passed


def test_number_lint_catches_hallucinations() -> None:
    metrics = {"outflow_usd": "1234.50"}

    # Hallucinated 9,999.99
    text = "The monthly burn was $9,999.99 across all accounts."
    res = lint_numbers(text, metrics)
    assert not res.passed
    assert any("9,999.99" in tok for tok in res.ungrounded_tokens)


def test_number_lint_catches_out_of_bounds_multiplier() -> None:
    metrics = {"outflow_usd": "1200000"}

    # 1.5M implies [1,450,000 .. 1,550,000], should not match 1,200,000
    text = "Outflows reached $1.5M this quarter."
    res = lint_numbers(text, metrics)
    assert not res.passed


# --- 2. Language Lint Tests ---

def test_language_lint_passes_associative_text() -> None:
    text = (
        "Net outflow increased from July to August. "
        "The change is concentrated in vendor transfers and coincides with the protocol upgrade."
    )
    res = lint_language(text)
    assert res.passed
    assert len(res.flagged_phrases) == 0


@pytest.mark.parametrize(
    "causal_text,expected_phrase",
    [
        ("The increase was caused by high network fees.", "caused by"),
        ("Outflows rose because marketing spent more.", "because"),
        ("New incentives led to increased trading volume.", "led to"),
        ("The drop was driven by market conditions.", "driven by"),
        ("This resulted in negative cash flow.", "resulted in"),
        ("Losses occurred as a result of price slippage.", "as a result of"),
    ],
)
def test_language_lint_blocks_causal_phrases(causal_text: str, expected_phrase: str) -> None:
    res = lint_language(causal_text)
    assert not res.passed
    assert expected_phrase in res.flagged_phrases
    assert len(res.suggestions) > 0


# --- 3. Evidence Status and Invariants ---

def test_segment_sum_invariant() -> None:
    # Exact decimal sum
    segments = [Decimal("100.25"), Decimal("200.50"), Decimal("699.25")]
    total = Decimal("1000.00")
    assert check_segment_sum_invariant(segments, total)

    # Broken sum
    bad_segments = [Decimal("100.00"), Decimal("200.00")]
    assert not check_segment_sum_invariant(bad_segments, total)


def test_percentage_invariant() -> None:
    # 148 / 1000 = 14.8%
    assert check_percentage_invariant(148, 1000, Decimal("14.8"))
    assert check_percentage_invariant(Decimal("148.1"), Decimal("1000"), Decimal("14.81"))
    # Inconsistent percentage
    assert not check_percentage_invariant(100, 1000, Decimal("25.0"))


def test_evaluate_evidence_status_logic() -> None:
    # 1. Clean verification
    status = evaluate_evidence_status(
        recompute_matches=True,
        claim_type="metric",
        invariants_passed=True,
        sample_size_ok=True,
        quality_issues_present=False,
    )
    assert status == "supported"

    # 2. Recompute failure
    status = evaluate_evidence_status(
        recompute_matches=False,
        claim_type="metric",
    )
    assert status == "insufficient"

    # 3. Quality caveats or active assumptions
    status = evaluate_evidence_status(
        recompute_matches=True,
        claim_type="metric",
        quality_issues_present=True,
    )
    assert status == "partially_supported"

    # 4. Definition or suggestion
    status = evaluate_evidence_status(
        recompute_matches=True,
        claim_type="suggestion",
    )
    assert status == "not_applicable"


# --- 4. Recomputation Verification ---

def test_recompute_spec_success(tmp_path: Path) -> None:
    # Prepare parquet
    csv_path = Path("fixtures/treasury_sample.csv")
    with open(csv_path, "rb") as f:
        df, _, _, c_hash, parquet_path, _ = normalize_dataset(
            filename="treasury_sample.csv",
            content=f.read(),
        )

    from datetime import date

    spec = AnalysisSpec(
        dataset_version_ids=["dv_test"],
        metrics=[MetricRef(name="outflow_usd")],
        time=TimeWindow(
            column="block_time",
            start=date(2026, 8, 1),
            end=date(2026, 8, 31),
        ),
    )

    backend = LocalBackend()
    load_metric_pack("treasury_v1")
    sql, params = compile_spec(spec, table_name="t")
    table_map = {"t": parquet_path}

    res1 = backend.execute_query(sql, params, table_map)
    expected_hash = hash_obj(res1.to_dict())

    # Recompute
    recompute_res = recompute_spec(
        spec=spec,
        expected_result_hash=expected_hash,
        table_map=table_map,
        backend=backend,
    )
    assert recompute_res.matches
    assert recompute_res.computed_hash == expected_hash

    # Tampered expected hash
    tampered_res = recompute_spec(
        spec=spec,
        expected_result_hash="0000000000000000000000000000000000000000000000000000000000000000",
        table_map=table_map,
        backend=backend,
    )
    assert not tampered_res.matches
