"""Evidence record builder with cryptographic provenance, reproduction proof, and JCS hashing per §7.4 and §8.5."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import json

from backend.backends.base import ExecutionBackend, QueryResult
from backend.core.hashing import hash_obj, jcs, sha256_hex
from backend.core.ids import generate_id
from backend.engine.models import AnalysisSpec, Evidence, RowRefs


def build_evidence(
    session_id: str,
    spec: AnalysisSpec,
    result: QueryResult,
    sql: str,
    params: list[Any],
    dataset_hashes: dict[str, str],
    backend: ExecutionBackend,
    table_map: dict[str, str],
    assumption_ids: list[str] | None = None,
) -> Evidence:
    """Construct an auditable Evidence record with cryptographic reproduction verification.

    Per §7.4 and §8.5:
    - spec_hash: sha256(JCS(spec))
    - result_hash: sha256(JCS(result))
    - row_refs: sample <= 50 identifiers, total, list_hash
    - metrics: named scalar values extracted from first row as decimal strings
    - reproduction: re-executes compiled query in a fresh connection to verify deterministic hash
    - evidence_hash: sha256(JCS(all fields except created_at, reproduced, evidence_hash))
    """
    evidence_id = generate_id("ev")
    now_dt = datetime.now(timezone.utc)

    # 1. Hashes of spec and result
    spec_dict = spec.model_dump(mode="json")
    spec_hash = hash_obj(spec_dict)

    result_dict = result.to_dict()
    result_hash = hash_obj(result_dict)

    # 2. Extract row references
    identifiers: list[str] = []
    kind = "row_index"
    sig_col_idx = None

    if "tx_signature" in result.columns:
        sig_col_idx = result.columns.index("tx_signature")
        kind = "tx_signature"

    for idx, row in enumerate(result.rows):
        if sig_col_idx is not None and sig_col_idx < len(row):
            identifiers.append(str(row[sig_col_idx]))
        else:
            identifiers.append(f"row_{idx}")

    sorted_identifiers = sorted(identifiers)
    sample_refs = sorted_identifiers[:50]
    list_hash = hash_obj(sorted_identifiers)

    row_refs = RowRefs(
        kind="tx_signature" if kind == "tx_signature" else "row_index",
        sample=sample_refs,
        total=result.row_count,
        list_hash=list_hash,
    )

    # 3. Scalar metrics dictionary for grounding citation
    metrics_map: dict[str, str | None] = {}
    if result.rows:
        first_row = result.rows[0]
        for col_name, val in zip(result.columns, first_row):
            # Include all metric values from first row as decimal strings
            if val is not None:
                metrics_map[col_name] = str(val)
            else:
                metrics_map[col_name] = None

    # 4. Mandatory reproduction check: re-run query independently and compare result_hash
    reproduced_result = backend.execute_query(sql, params, table_map)
    reproduced_hash = hash_obj(reproduced_result.to_dict())
    is_reproduced = (reproduced_hash == result_hash)

    # 5. Compute evidence_hash over frozen fields
    frozen_payload = {
        "id": evidence_id,
        "session_id": session_id,
        "spec": spec_dict,
        "spec_hash": spec_hash,
        "dataset_version_ids": spec.dataset_version_ids,
        "dataset_hashes": dataset_hashes,
        "query_sql": sql,
        "query_params": [str(p) for p in params],
        "result": result_dict,
        "result_hash": result_hash,
        "rows_used": result.row_count,
        "row_refs": row_refs.model_dump(mode="json"),
        "metrics": metrics_map,
        "assumption_ids": assumption_ids or [],
        "engine_version": "0.1.0",
        "created_by": "engine",
    }
    evidence_hash = hash_obj(frozen_payload)

    return Evidence(
        id=evidence_id,
        session_id=session_id,
        spec=spec,
        spec_hash=spec_hash,
        dataset_version_ids=spec.dataset_version_ids,
        dataset_hashes=dataset_hashes,
        query_sql=sql,
        query_params=params,
        result=result_dict,
        result_hash=result_hash,
        rows_used=result.row_count,
        row_refs=row_refs,
        metrics=metrics_map,
        assumption_ids=assumption_ids or [],
        engine_version="0.1.0",
        created_by="engine",
        created_at=now_dt,
        reproduced=is_reproduced,
        evidence_hash=evidence_hash,
    )
