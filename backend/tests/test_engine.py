"""Golden test suite over fixtures/treasury_golden.json per §8.5 and §14.

100% exact match to the cent. Runs with NO LLM.
"""

from decimal import Decimal
import json
from pathlib import Path
import tempfile
import pandas as pd
import pytest

from backend.backends.local import LocalBackend
from backend.core.hashing import canonical_table_hash
from backend.engine.contribution import analyze_contribution
from backend.engine.execute import execute_analysis
from backend.engine.models import AnalysisSpec
from backend.engine.sufficiency import check_sufficiency
from backend.engine.sufficiency_models import Requirement
from backend.semantic.metrics import MetricPackRegistry


@pytest.fixture(scope="module")
def treasury_setup():
    """Load treasury sample CSV and register treasury_v1 metric pack."""
    csv_path = Path("fixtures/treasury_sample.csv")
    golden_path = Path("fixtures/treasury_golden.json")
    pack_path = Path("metric_packs/treasury_v1.yaml")

    assert csv_path.exists(), f"Missing {csv_path}"
    assert golden_path.exists(), f"Missing {golden_path}"
    assert pack_path.exists(), f"Missing {pack_path}"

    registry = MetricPackRegistry()
    registry.load_from_yaml(pack_path)

    df = pd.read_csv(csv_path)

    # Save to temp parquet
    tmp_dir = tempfile.mkdtemp()
    parquet_path = str(Path(tmp_dir) / "treasury.parquet")
    df_parquet = df.copy()
    df_parquet["block_time"] = pd.to_datetime(df_parquet["block_time"], utc=True)
    df_parquet.to_parquet(parquet_path, engine="pyarrow", index=False)

    c_hash = canonical_table_hash(df)
    with open(golden_path, "r", encoding="utf-8") as f:
        golden_cases = {case["id"]: case for case in json.load(f)}

    table_map = {"t": parquet_path}
    dataset_hashes = {"dv_treasury_sample": c_hash}
    available_cols = list(df.columns)

    return {
        "df": df,
        "golden_cases": golden_cases,
        "table_map": table_map,
        "dataset_hashes": dataset_hashes,
        "available_cols": available_cols,
        "registry": registry,
        "backend": LocalBackend(),
    }


def test_golden_outflow_last_complete_month(treasury_setup) -> None:
    case = treasury_setup["golden_cases"]["outflow_last_complete_month"]
    spec = AnalysisSpec(**case["spec"])

    evidence, result = execute_analysis(
        spec=spec,
        session_id="ses_golden",
        table_map=treasury_setup["table_map"],
        dataset_hashes=treasury_setup["dataset_hashes"],
        available_columns=treasury_setup["available_cols"],
        backend=treasury_setup["backend"],
        registry=treasury_setup["registry"],
    )

    assert evidence.reproduced is True
    assert evidence.metrics["outflow_usd"] == case["expected_metrics"]["outflow_usd"]


def test_golden_inflow_last_complete_month(treasury_setup) -> None:
    case = treasury_setup["golden_cases"]["inflow_last_complete_month"]
    spec = AnalysisSpec(**case["spec"])

    evidence, result = execute_analysis(
        spec=spec,
        session_id="ses_golden",
        table_map=treasury_setup["table_map"],
        dataset_hashes=treasury_setup["dataset_hashes"],
        available_columns=treasury_setup["available_cols"],
        backend=treasury_setup["backend"],
        registry=treasury_setup["registry"],
    )

    assert evidence.reproduced is True
    assert evidence.metrics["inflow_usd"] == case["expected_metrics"]["inflow_usd"]


def test_golden_net_flow_last_complete_month(treasury_setup) -> None:
    case = treasury_setup["golden_cases"]["net_flow_last_complete_month"]
    spec = AnalysisSpec(**case["spec"])

    evidence, result = execute_analysis(
        spec=spec,
        session_id="ses_golden",
        table_map=treasury_setup["table_map"],
        dataset_hashes=treasury_setup["dataset_hashes"],
        available_columns=treasury_setup["available_cols"],
        backend=treasury_setup["backend"],
        registry=treasury_setup["registry"],
    )

    assert evidence.reproduced is True
    assert evidence.metrics["net_flow_usd"] == case["expected_metrics"]["net_flow_usd"]


def test_golden_tx_count(treasury_setup) -> None:
    case = treasury_setup["golden_cases"]["tx_count"]
    spec = AnalysisSpec(**case["spec"])

    evidence, result = execute_analysis(
        spec=spec,
        session_id="ses_golden",
        table_map=treasury_setup["table_map"],
        dataset_hashes=treasury_setup["dataset_hashes"],
        available_columns=treasury_setup["available_cols"],
        backend=treasury_setup["backend"],
        registry=treasury_setup["registry"],
    )

    assert evidence.reproduced is True
    assert evidence.metrics["tx_count"] == case["expected_metrics"]["tx_count"]


def test_golden_unique_counterparties(treasury_setup) -> None:
    case = treasury_setup["golden_cases"]["unique_counterparties"]
    spec = AnalysisSpec(**case["spec"])

    evidence, result = execute_analysis(
        spec=spec,
        session_id="ses_golden",
        table_map=treasury_setup["table_map"],
        dataset_hashes=treasury_setup["dataset_hashes"],
        available_columns=treasury_setup["available_cols"],
        backend=treasury_setup["backend"],
        registry=treasury_setup["registry"],
    )

    assert evidence.reproduced is True
    assert evidence.metrics["unique_counterparties"] == case["expected_metrics"]["unique_counterparties"]


def test_golden_top_5_counterparties_outflow(treasury_setup) -> None:
    case = treasury_setup["golden_cases"]["top_5_counterparties_outflow"]
    spec = AnalysisSpec(**case["spec"])

    evidence, result = execute_analysis(
        spec=spec,
        session_id="ses_golden",
        table_map=treasury_setup["table_map"],
        dataset_hashes=treasury_setup["dataset_hashes"],
        available_columns=treasury_setup["available_cols"],
        backend=treasury_setup["backend"],
        registry=treasury_setup["registry"],
    )

    assert evidence.reproduced is True
    assert len(result.rows) == 5

    exp = case["expected_metrics"]
    assert result.rows[0][0] == exp["top_1_counterparty"]
    assert str(result.rows[0][1]) == exp["top_1_amount"]
    assert result.rows[1][0] == exp["top_2_counterparty"]
    assert str(result.rows[1][1]) == exp["top_2_amount"]


def test_golden_month_over_month_change(treasury_setup) -> None:
    case = treasury_setup["golden_cases"]["month_over_month_outflow_change"]
    spec = AnalysisSpec(**case["spec"])

    evidence, result = execute_analysis(
        spec=spec,
        session_id="ses_golden",
        table_map=treasury_setup["table_map"],
        dataset_hashes=treasury_setup["dataset_hashes"],
        available_columns=treasury_setup["available_cols"],
        backend=treasury_setup["backend"],
        registry=treasury_setup["registry"],
    )

    assert evidence.reproduced is True
    exp = case["expected_metrics"]
    curr_val = evidence.metrics.get("current_outflow_usd")
    base_val = evidence.metrics.get("baseline_outflow_usd")
    assert curr_val == exp["current_outflow_usd"]
    assert base_val == exp["baseline_outflow_usd"]


def test_golden_contribution_spike(treasury_setup) -> None:
    case = treasury_setup["golden_cases"]["contribution_spike_counterparty"]
    spec = AnalysisSpec(**case["spec"])

    evidence, result = execute_analysis(
        spec=spec,
        session_id="ses_golden",
        table_map=treasury_setup["table_map"],
        dataset_hashes=treasury_setup["dataset_hashes"],
        available_columns=treasury_setup["available_cols"],
        backend=treasury_setup["backend"],
        registry=treasury_setup["registry"],
    )

    # Transform result into segment dictionaries
    segment_dicts = [
        {"counterparty": r[0], "current_outflow_usd": r[1], "baseline_outflow_usd": r[2]}
        for r in result.rows
    ]
    report = analyze_contribution(
        segment_data=segment_dicts,
        dimension_col="counterparty",
        current_metric_col="current_outflow_usd",
        baseline_metric_col="baseline_outflow_usd",
        group_other=True,
    )

    top_seg = report.segments[0]
    exp = case["expected_metrics"]
    assert top_seg.segment == exp["spike_counterparty"]
    assert top_seg.current_value == exp["current_amount"]
    assert top_seg.baseline_value == exp["baseline_amount"]
    assert top_seg.share_of_change_pct == exp["share_of_change_pct"]
    assert top_seg.is_concentrated is True


def test_golden_runway_valid(treasury_setup) -> None:
    case = treasury_setup["golden_cases"]["runway_valid"]
    orig_spec = AnalysisSpec(**case["spec"])
    spec = AnalysisSpec(
        dataset_version_ids=["dv_treasury_sample"],
        metrics=[{"name": "outflow_usd"}, {"name": "inflow_usd"}],
        time=orig_spec.time,
        filters=[{"column": "tx_status", "op": "=", "value": "success"}],
    )

    evidence, result = execute_analysis(
        spec=spec,
        session_id="ses_golden",
        table_map=treasury_setup["table_map"],
        dataset_hashes=treasury_setup["dataset_hashes"],
        available_columns=treasury_setup["available_cols"],
        backend=treasury_setup["backend"],
        registry=treasury_setup["registry"],
    )

    outflow = Decimal(evidence.metrics["outflow_usd"])
    inflow = Decimal(evidence.metrics["inflow_usd"])
    net_burn_3mo = outflow - inflow
    avg_monthly_net_burn = net_burn_3mo / Decimal(3)

    treasury_bal = Decimal("10000000.00")
    runway_months = treasury_bal / avg_monthly_net_burn

    exp = case["expected_metrics"]
    assert f"{avg_monthly_net_burn:.2f}" == exp["avg_monthly_net_burn_usd"]
    assert f"{runway_months:.2f}" == exp["runway_months"]


def test_golden_runway_incomplete_history(treasury_setup) -> None:
    case = treasury_setup["golden_cases"]["runway_incomplete_history"]
    df = treasury_setup["df"]

    # Sufficiency check with incomplete history
    reqs = [
        Requirement(role="outflow_usd", min_coverage="0.90"),
        Requirement(role="direction", min_coverage="0.90"),
    ]
    res = check_sufficiency(df, reqs, complete_history=False)
    assert res.verdict == case["expected_metrics"]["verdict"]
    assert "complete_history" in res.missing
