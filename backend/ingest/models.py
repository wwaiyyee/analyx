"""Pydantic domain models for dataset ingestion, schemas, transformations, and quality."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class ColumnSchema(BaseModel):
    """Schema definition for a single column."""

    name: str
    dtype: Literal["string", "int", "decimal", "bool", "date", "datetime", "list"]
    nullable: bool = True


class TransformationStep(BaseModel):
    """Auditable transformation applied during ingestion."""

    id: str
    operation: str  # e.g. "drop_totals_row", "parse_locale_number", "unpivot", "select_sheet"
    parameters: dict[str, Any] = Field(default_factory=dict)
    rows_before: int
    rows_after: int
    requires_approval: bool = False  # True if totals or row counts are altered
    approved_by_user: bool | None = None


class QualityIssue(BaseModel):
    """Data quality diagnostic issue identified during profiling."""

    severity: Literal["info", "warning", "error"]
    category: Literal["totals_row", "nulls", "outliers", "pii", "types", "duplicates", "constant"]
    column: str | None = None
    description: str
    details: dict[str, Any] = Field(default_factory=dict)


class ColumnProfile(BaseModel):
    """Detailed statistical profile for a single column."""

    name: str
    inferred_dtype: str
    null_count: int
    null_ratio: str  # Decimal string e.g. "0.05"
    distinct_count: int
    min_value: str | None = None
    max_value: str | None = None
    sample_values: list[str] = Field(default_factory=list)
    is_pii: bool = False
    pii_type: str | None = None


class QualityReport(BaseModel):
    """Comprehensive dataset quality diagnostic report."""

    dataset_name: str
    total_rows: int
    total_columns: int
    columns: list[ColumnProfile] = Field(default_factory=list)
    issues: list[QualityIssue] = Field(default_factory=list)
    created_at: datetime
