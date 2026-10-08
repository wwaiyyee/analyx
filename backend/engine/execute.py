"""Execution orchestrator coordinating validation, compilation, execution, and evidence building."""

from typing import Any, Tuple

from backend.backends.base import ExecutionBackend, QueryResult
from backend.backends.local import LocalBackend
from backend.engine.compile import compile_spec
from backend.engine.evidence import build_evidence
from backend.engine.models import AnalysisSpec, Evidence
from backend.engine.spec import validate_spec
from backend.semantic.metrics import MetricPackRegistry, default_registry


def execute_analysis(
    spec: AnalysisSpec,
    session_id: str,
    table_map: dict[str, str],
    dataset_hashes: dict[str, str],
    available_columns: list[str],
    backend: ExecutionBackend | None = None,
    registry: MetricPackRegistry | None = None,
    assumption_ids: list[str] | None = None,
) -> Tuple[Evidence, QueryResult]:
    """Execute complete analysis pipeline: validate spec -> compile SQL -> run backend -> construct evidence."""
    reg = registry or default_registry
    exec_backend = backend or LocalBackend()

    # 1. Validate spec against schema and metric packs
    validate_spec(spec, available_columns=available_columns, registry=reg)

    # 2. Compile spec into parameterized SQL query
    # Use 't' as default single-table alias
    table_alias = "t"
    sql, params = compile_spec(spec, table_name=table_alias, registry=reg)

    # If table_map has only 1 entry and key is not 't', bind it to 't'
    if len(table_map) == 1 and table_alias not in table_map:
        only_path = next(iter(table_map.values()))
        table_map = {table_alias: only_path}

    # 3. Execute query on analytical execution backend
    query_result = exec_backend.execute_query(sql, params, table_map)

    # 4. Build Evidence with cryptographic reproduction verification
    evidence = build_evidence(
        session_id=session_id,
        spec=spec,
        result=query_result,
        sql=sql,
        params=params,
        dataset_hashes=dataset_hashes,
        backend=exec_backend,
        table_map=table_map,
        assumption_ids=assumption_ids,
    )

    return evidence, query_result
