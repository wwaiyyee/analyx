"""Deterministic Vega-Lite chart builder mapping evidence data shapes to charts per §8.9."""

import json
from typing import Any, Literal

ChartIntent = Literal["trend", "compare", "bridge", "composition"]


def build_chart(
    finding: dict[str, Any],
    evidence: dict[str, Any],
    intent: ChartIntent = "compare",
    title: str | None = None,
) -> dict[str, Any]:
    """Map evidence results deterministically into Vega-Lite JSON schema."""
    claim = finding.get("claim", "Analytical Visualization")
    chart_title = title or claim

    repro = evidence.get("reproduction", {})
    metrics = evidence.get("metrics", {})
    # Extract tabular data points from evidence
    records = evidence.get("data", [])
    if not records and "rows" in evidence.get("result", {}):
        res = evidence["result"]
        cols = res.get("columns", [])
        records = [{cols[i]: val for i, val in enumerate(r)} for r in res.get("rows", [])]

    # Fallback to single metric bar if records empty
    if not records:
        records = [{"metric": k, "value": float(v) if v is not None else 0.0} for k, v in metrics.items()]

    base_spec: dict[str, Any] = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": chart_title,
        "data": {"values": records},
    }

    if intent == "trend":
        # Line or Bar chart over date/period
        date_col = next((c for c in records[0].keys() if any(k in c.lower() for k in ("date", "time", "day", "month"))), "date")
        measure_col = next((c for c in records[0].keys() if c != date_col), "value")
        mark_type = "bar" if len(records) <= 6 else "line"

        base_spec.update({
            "mark": {"type": mark_type, "point": mark_type == "line"},
            "encoding": {
                "x": {"field": date_col, "type": "temporal" if "time" in date_col.lower() else "ordinal", "title": "Period"},
                "y": {"field": measure_col, "type": "quantitative", "scale": {"zero": True}, "title": measure_col},
                "tooltip": [{"field": date_col}, {"field": measure_col, "format": ",.2f"}],
            },
        })

    elif intent == "compare":
        # Horizontal bar chart sorted descending
        cat_col = next((c for c in records[0].keys() if any(k in c.lower() for k in ("name", "category", "counterparty", "dim", "segment", "metric"))), list(records[0].keys())[0])
        val_col = next((c for c in records[0].keys() if c != cat_col), list(records[0].keys())[-1])

        base_spec.update({
            "mark": "bar",
            "encoding": {
                "y": {"field": cat_col, "type": "nominal", "sort": "-x", "title": "Category"},
                "x": {"field": val_col, "type": "quantitative", "scale": {"zero": True}, "title": "Amount"},
                "tooltip": [{"field": cat_col}, {"field": val_col, "format": ",.2f"}],
            },
        })

    elif intent == "composition":
        cat_col = next((c for c in records[0].keys() if any(k in c.lower() for k in ("name", "category", "counterparty", "dim", "segment", "metric"))), list(records[0].keys())[0])
        val_col = next((c for c in records[0].keys() if c != cat_col), list(records[0].keys())[-1])

        if len(records) <= 5:
            # Pie / arc chart
            base_spec.update({
                "mark": {"type": "arc", "innerRadius": 30},
                "encoding": {
                    "theta": {"field": val_col, "type": "quantitative"},
                    "color": {"field": cat_col, "type": "nominal"},
                    "tooltip": [{"field": cat_col}, {"field": val_col, "format": ",.2f"}],
                },
            })
        else:
            # Stacked normalized bar
            base_spec.update({
                "mark": "bar",
                "encoding": {
                    "x": {"field": val_col, "type": "quantitative", "stack": "normalize", "title": "Share"},
                    "color": {"field": cat_col, "type": "nominal", "sort": "-x"},
                    "tooltip": [{"field": cat_col}, {"field": val_col, "format": ",.2f"}],
                },
            })

    elif intent == "bridge":
        # Waterfall delta representation
        driver_col = next((c for c in records[0].keys() if any(k in c.lower() for k in ("driver", "segment", "category", "counterparty"))), list(records[0].keys())[0])
        delta_col = next((c for c in records[0].keys() if any(k in c.lower() for k in ("delta", "change", "diff", "value"))), list(records[0].keys())[-1])

        base_spec.update({
            "mark": "bar",
            "encoding": {
                "x": {"field": driver_col, "type": "nominal", "title": "Driver"},
                "y": {"field": delta_col, "type": "quantitative", "scale": {"zero": True}, "title": "Change"},
                "color": {
                    "condition": {"test": f"datum.{delta_col} >= 0", "value": "#10B981"},
                    "value": "#EF4444",
                },
                "tooltip": [{"field": driver_col}, {"field": delta_col, "format": ",.2f"}],
            },
        })

    return base_spec
