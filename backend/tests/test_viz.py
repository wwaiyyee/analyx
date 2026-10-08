"""Unit tests for Vega-Lite visualization builder and chart linter per §8.9."""

from backend.viz.builder import build_chart
from backend.viz.lint import lint_chart


def test_build_chart_intents() -> None:
    finding = {"claim": "August had highest outflow"}
    evidence = {
        "metrics": {"outflow_usd": "125000.00"},
        "result": {
            "columns": ["counterparty", "amount_usd"],
            "rows": [
                ["Vendor_A", 50000.00],
                ["Vendor_B", 35000.00],
                ["Vendor_C", 20000.00],
            ],
        },
    }

    # 1. Compare intent
    spec_compare = build_chart(finding, evidence, intent="compare")
    assert spec_compare["mark"] == "bar"
    assert spec_compare["encoding"]["y"]["type"] == "nominal"
    assert spec_compare["encoding"]["x"]["type"] == "quantitative"
    assert spec_compare["encoding"]["x"]["scale"]["zero"] is True

    lint_res = lint_chart(spec_compare)
    assert lint_res.passed

    # 2. Trend intent
    trend_ev = {
        "result": {
            "columns": ["date", "outflow_usd"],
            "rows": [
                ["2026-06", 10000.00],
                ["2026-07", 15000.00],
                ["2026-08", 25000.00],
            ],
        }
    }
    spec_trend = build_chart(finding, trend_ev, intent="trend")
    assert "encoding" in spec_trend
    lint_trend = lint_chart(spec_trend)
    assert lint_trend.passed

    # 3. Bridge intent (waterfall)
    bridge_ev = {
        "result": {
            "columns": ["driver", "delta_usd"],
            "rows": [
                ["Vendor_Spike", 15000.00],
                ["Marketing_Drop", -5000.00],
            ],
        }
    }
    spec_bridge = build_chart(finding, bridge_ev, intent="bridge")
    assert spec_bridge["mark"] == "bar"
    assert "color" in spec_bridge["encoding"]
    lint_bridge = lint_chart(spec_bridge)
    assert lint_bridge.passed

    # 4. Composition intent
    spec_comp = build_chart(finding, evidence, intent="composition")
    assert "mark" in spec_comp
    lint_comp = lint_chart(spec_comp)
    assert lint_comp.passed


def test_chart_lint_catches_truncated_axis() -> None:
    bad_spec = {
        "title": "Misleading Truncated Chart",
        "mark": "bar",
        "encoding": {
            "x": {"field": "val", "type": "quantitative", "scale": {"zero": False}},
            "y": {"field": "cat", "type": "nominal"},
        },
        "data": {"values": [{"cat": "A", "val": 100}, {"cat": "B", "val": 105}]},
    }
    res = lint_chart(bad_spec)
    assert not res.passed
    assert any("zero" in err.lower() for err in res.errors)


def test_chart_lint_catches_missing_title() -> None:
    spec_no_title = {
        "title": "",
        "mark": "bar",
        "encoding": {},
        "data": {"values": []},
    }
    res = lint_chart(spec_no_title)
    assert not res.passed
    assert any("title" in err.lower() for err in res.errors)
