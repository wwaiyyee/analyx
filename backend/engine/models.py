"""Pydantic domain models for the analysis engine, specs, evidence, and findings.

Per blueprint §7.3 and §7.4:
- Float values are strictly disallowed in specs and evidence; decimal strings are used instead.
- Evidence objects are produced ONLY by deterministic engine execution.
"""

from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class TimeWindow(BaseModel):
    """Temporal filter and aggregation grain specification."""

    column: str
    start: date | None = None
    end: date | None = None  # Inclusive
    grain: Literal["day", "week", "month", "quarter", "year"] | None = None


class Filter(BaseModel):
    """Deterministic predicate filter."""

    column: str
    op: Literal["=", "!=", ">", ">=", "<", "<=", "in", "not_in", "between", "is_null", "not_null"]
    value: Any = None  # Stored as decimal strings, integers, strings, or lists; never float


class MetricRef(BaseModel):
    """Reference to a registered metric in a loaded metric pack."""

    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class Comparison(BaseModel):
    """Period-over-period or baseline comparison specification."""

    kind: Literal["none", "period_over_period", "vs_baseline"] = "none"
    baseline: TimeWindow | None = None


class AnalysisSpec(BaseModel):
    """Complete specification for a deterministic data query/analysis."""

    dataset_version_ids: list[str]
    metrics: list[MetricRef]
    dimensions: list[str] = Field(default_factory=list)
    filters: list[Filter] = Field(default_factory=list)
    time: TimeWindow | None = None
    comparison: Comparison = Field(default_factory=Comparison)
    contribution_of: str | None = None  # Dimension for contribution analysis
    order_by: str | None = None
    descending: bool = True
    limit: int | None = Field(default=None, le=1000)


class RowRefs(BaseModel):
    """Cryptographic provenance sample and full-list hash of underlying rows."""

    kind: Literal["tx_signature", "row_index"]
    sample: list[str] = Field(default_factory=list, max_length=50)  # <= 50 identifiers
    total: int
    list_hash: str  # SHA-256 of JCS(sorted full identifier list)


class Evidence(BaseModel):
    """Deterministic computational evidence record with reproduction proof."""

    id: str
    session_id: str
    spec: AnalysisSpec
    spec_hash: str  # sha256(JCS(spec))
    dataset_version_ids: list[str]
    dataset_hashes: dict[str, str]
    query_sql: str
    query_params: list[Any] = Field(default_factory=list)
    result: dict[str, Any]  # {"columns": [...], "rows": [[...]]}, numbers as decimal strings
    result_hash: str
    rows_used: int
    row_refs: RowRefs
    metrics: dict[str, str | None] = Field(default_factory=dict)  # Named scalar decimal strings
    assumption_ids: list[str] = Field(default_factory=list)
    engine_version: str = "0.1.0"
    created_by: Literal["engine"] = "engine"
    created_at: datetime
    reproduced: bool = True
    evidence_hash: str  # sha256(JCS(all fields except created_at, reproduced, evidence_hash))


class ValidationCheck(BaseModel):
    """Result of an individual integrity check."""

    name: str
    passed: bool
    detail: str | None = None


class Finding(BaseModel):
    """Grounded analytical finding linked directly to evidence."""

    id: str
    session_id: str
    claim_text: str
    claim_type: Literal["observed", "calculated", "inferred", "unknown"]
    strength: Literal["descriptive", "associational", "causal"]  # "causal" prohibited in P0
    evidence_ids: list[str] = Field(default_factory=list)
    metric_keys: list[str] = Field(default_factory=list)  # Keys in Evidence.metrics cited in claim
    evidence_status: Literal["supported", "partially_supported", "insufficient", "not_applicable"]
    validation: list[ValidationCheck] = Field(default_factory=list)
    stale: bool = False


class Assumption(BaseModel):
    """Explicit domain or heuristic assumption tracked across sessions."""

    id: str
    session_id: str
    text: str
    source: Literal["system", "user", "llm"] = "system"
    affects_finding_ids: list[str] = Field(default_factory=list)
    status: Literal["active", "revised"] = "active"


class Chart(BaseModel):
    """Visualization spec paired with a finding and evidence."""

    id: str
    finding_id: str
    intent: Literal["trend", "compare", "bridge", "composition", "distribution", "relationship"]
    vega_lite_spec: dict[str, Any]
    evidence_id: str
