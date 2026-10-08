"""Independent deterministic query recomputation and result hash verification per §8.8 (3)."""

from dataclasses import dataclass
from typing import Any

from backend.backends.base import ExecutionBackend
from backend.backends.local import LocalBackend
from backend.core.hashing import hash_obj
from backend.engine.compile import compile_spec
from backend.engine.models import AnalysisSpec
from backend.semantic.metrics import load_metric_pack


@dataclass
class RecomputeResult:
    matches: bool
    computed_hash: str
    expected_hash: str
    row_count: int
    columns: list[str]


def recompute_spec(
    spec: AnalysisSpec | dict[str, Any],
    expected_result_hash: str,
    table_map: dict[str, str],
    backend: ExecutionBackend | None = None,
    metric_pack_name: str = "treasury_v1",
) -> RecomputeResult:
    """Execute spec query independently in an isolated backend session and verify result_hash."""
    if isinstance(spec, dict):
        spec = AnalysisSpec.model_validate(spec)

    exec_backend = backend or LocalBackend()
    metric_pack = load_metric_pack(metric_pack_name)
    sql, params = compile_spec(spec, metric_pack)

    query_res = exec_backend.execute_query(
        sql=sql,
        params=params,
        table_map=table_map,
    )

    computed_hash = hash_obj(query_res.to_dict())
    matches = (computed_hash == expected_result_hash)

    return RecomputeResult(
        matches=matches,
        computed_hash=computed_hash,
        expected_hash=expected_result_hash,
        row_count=query_res.row_count,
        columns=query_res.columns,
    )
