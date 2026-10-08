"""AnalysisSpec validation per §8.5: column allow-lists, metric registration, and parameter typing."""

from typing import Iterable
from backend.core.errors import FloatNotAllowedError, ValidationError
from backend.engine.models import AnalysisSpec, Filter
from backend.semantic.metrics import MetricPackRegistry, default_registry

MAX_SPEC_LIMIT = 1000
ALLOWED_OPS = {"=", "!=", ">", ">=", "<", "<=", "in", "not_in", "between", "is_null", "not_null"}


def _validate_filter_value(val: object) -> None:
    """Ensure filter values contain no floats."""
    if isinstance(val, float):
        raise FloatNotAllowedError(f"Filter value cannot be a float ({val}). Use decimal string or integer.")
    if isinstance(val, (list, tuple)):
        for item in val:
            _validate_filter_value(item)
    elif isinstance(val, dict):
        for v in val.values():
            _validate_filter_value(v)


def validate_spec(
    spec: AnalysisSpec,
    available_columns: Iterable[str],
    registry: MetricPackRegistry | None = None,
) -> AnalysisSpec:
    """Validate AnalysisSpec against dictionary columns and loaded metric packs.

    Raises ValidationError or FloatNotAllowedError if constraints are violated.
    """
    col_set = set(available_columns)
    pack_reg = registry or default_registry

    # 1. Dataset version IDs
    if not spec.dataset_version_ids:
        raise ValidationError("AnalysisSpec must specify at least one dataset_version_id")

    # 2. Limit constraint
    if spec.limit is not None:
        if spec.limit < 1 or spec.limit > MAX_SPEC_LIMIT:
            raise ValidationError(f"Spec limit must be between 1 and {MAX_SPEC_LIMIT}, got {spec.limit}")

    # 3. Dimensions allow-list
    for dim in spec.dimensions:
        if dim not in col_set:
            raise ValidationError(f"Dimension column '{dim}' does not exist in dataset schema")

    # 4. Filters allow-list and float check
    for flt in spec.filters:
        if flt.column not in col_set:
            raise ValidationError(f"Filter column '{flt.column}' does not exist in dataset schema")
        if flt.op not in ALLOWED_OPS:
            raise ValidationError(f"Unsupported filter operator '{flt.op}'")
        _validate_filter_value(flt.value)

    # 5. Time window
    if spec.time:
        if spec.time.column not in col_set:
            raise ValidationError(f"Time window column '{spec.time.column}' does not exist in dataset schema")

    # 6. Metrics existence and required columns
    if not spec.metrics:
        raise ValidationError("AnalysisSpec must specify at least one metric")

    for m_ref in spec.metrics:
        # Validate that metric exists in registry
        missing_cols = pack_reg.validate_columns_for_metric(m_ref.name, list(col_set))
        if missing_cols:
            raise ValidationError(
                f"Metric '{m_ref.name}' requires column(s) {missing_cols} which are missing from dataset"
            )

    # 7. Contribution analysis dimension check
    if spec.contribution_of and spec.contribution_of not in col_set:
        raise ValidationError(f"Contribution dimension '{spec.contribution_of}' does not exist in dataset")

    return spec
