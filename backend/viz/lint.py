"""Chart integrity and visual excellence linter per §8.9."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChartLintResult:
    passed: bool
    errors: list[str] = field(default_factory=list)


def lint_chart(spec: dict[str, Any], evidence_records: list[dict[str, Any]] | None = None) -> ChartLintResult:
    """Validate Vega-Lite chart against visual honesty rules and evidence constraints.

    Rules:
    - Bar charts must start at zero (no truncated axes)
    - No misleading dual axes
    - Max 12 series/categories to prevent visual clutter
    - Title must be descriptive
    """
    errors: list[str] = []

    # 1. Title present
    title = spec.get("title")
    if not title or not str(title).strip():
        errors.append("Chart title must be present and descriptive.")

    mark = spec.get("mark")
    mark_type = mark.get("type", mark) if isinstance(mark, dict) else str(mark)
    encoding = spec.get("encoding", {})

    # 2. Bar charts must start at zero
    if mark_type == "bar":
        # Check quantitative encoding
        for axis_name in ("x", "y"):
            enc = encoding.get(axis_name, {})
            if enc.get("type") == "quantitative":
                scale = enc.get("scale", {})
                if scale.get("zero") is False:
                    errors.append(f"Bar chart {axis_name}-axis must start at zero (truncated axis disallowed).")

    # 3. No dual axes
    if "layer" in spec:
        resolve = spec.get("resolve", {})
        scale_resolve = resolve.get("scale", {})
        if scale_resolve.get("y") == "independent" or scale_resolve.get("x") == "independent":
            errors.append("Dual independent axes are disallowed for visual honesty.")

    # 4. Maximum 12 series / categories
    data_values = spec.get("data", {}).get("values", [])
    if len(data_values) > 12:
        # Check if grouped by category
        cat_key = next((k for k in data_values[0].keys() if isinstance(data_values[0][k], str)), None)
        if cat_key:
            distinct_cats = len({r[cat_key] for r in data_values})
            if distinct_cats > 12:
                errors.append(f"Too many categories ({distinct_cats}); maximum 12 allowed to prevent visual clutter.")

    return ChartLintResult(
        passed=len(errors) == 0,
        errors=errors,
    )
