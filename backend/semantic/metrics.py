"""Metric pack loader and registry validating YAML definitions per §8.3."""

from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
import yaml

from backend.core.errors import ValidationError


class MetricDefinition(BaseModel):
    """Specification of an analytical metric compiled into parameterized SQL."""

    name: str
    sql: str
    requires: list[str] = Field(default_factory=list)
    description: str = ""
    unit: str | None = None
    is_derived: bool = False
    derivation_rule: str | None = None


class MetricPack(BaseModel):
    """Collection of related metrics for a domain schema."""

    name: str
    requires_table: str = ""
    metrics: dict[str, MetricDefinition] = Field(default_factory=dict)


class MetricPackRegistry:
    """In-memory catalog of loaded metric packs."""

    def __init__(self) -> None:
        self._packs: dict[str, MetricPack] = {}

    def load_from_yaml(self, path: Path | str) -> MetricPack:
        """Parse and register a YAML metric pack definition."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Metric pack file not found: {p}")

        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return self.load_from_dict(data)

    def load_from_dict(self, data: dict[str, Any]) -> MetricPack:
        """Parse dictionary into MetricPack."""
        pack_name = data.get("pack", "unnamed_pack")
        requires_table = data.get("requires_table", "")
        raw_metrics = data.get("metrics", {})

        metrics_map: dict[str, MetricDefinition] = {}
        for m_name, m_spec in raw_metrics.items():
            metrics_map[m_name] = MetricDefinition(
                name=m_name,
                sql=m_spec.get("sql", ""),
                requires=m_spec.get("requires", []),
                description=m_spec.get("description", ""),
                unit=m_spec.get("unit"),
                is_derived=m_spec.get("is_derived", False),
                derivation_rule=m_spec.get("derivation_rule"),
            )

        pack = MetricPack(
            name=pack_name,
            requires_table=requires_table,
            metrics=metrics_map,
        )
        self._packs[pack_name] = pack
        return pack

    def get_pack(self, name: str) -> MetricPack | None:
        return self._packs.get(name)

    def find_metric(self, metric_name: str) -> MetricDefinition | None:
        """Find a metric by name across all registered packs."""
        for pack in self._packs.values():
            if metric_name in pack.metrics:
                return pack.metrics[metric_name]
        return None

    def validate_columns_for_metric(
        self,
        metric_name: str,
        available_columns: list[str],
    ) -> list[str]:
        """Check if all required columns for metric exist in dataset. Returns missing columns."""
        metric = self.find_metric(metric_name)
        if not metric:
            raise ValidationError(f"Metric '{metric_name}' is not registered in any loaded pack")

        available_set = set(available_columns)
        missing = [col for col in metric.requires if col not in available_set]
        return missing


default_registry = MetricPackRegistry()
