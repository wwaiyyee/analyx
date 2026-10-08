"""Evidence inspection, row retrieval, and reproduction proof endpoints."""

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
import pandas as pd
from sqlmodel import Session, select

from backend.api.auth import get_current_workspace
from backend.backends.local import LocalBackend
from backend.core.hashing import hash_obj
from backend.db.models import AnalysisSession, DatasetVersion, Evidence, Workspace
from backend.db.session import get_session
from backend.engine.compile import compile_spec
from backend.engine.models import AnalysisSpec
from backend.semantic.metrics import load_metric_pack

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/{evidence_id}")
def get_evidence(
    evidence_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get high-level evidence record without heavy raw row payload."""
    ev = session.get(Evidence, evidence_id)
    if not ev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Evidence {evidence_id} not found"}},
        )

    # Verify workspace ownership via session
    ses = session.get(AnalysisSession, ev.session_id)
    if not ses or ses.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Evidence {evidence_id} not found"}},
        )

    return {
        "id": ev.id,
        "session_id": ev.session_id,
        "sha256": ev.sha256,
        "result_hash": ev.result_hash,
        "spec": json.loads(ev.spec_json),
        "metrics": json.loads(ev.metrics_json),
        "reproduction": json.loads(ev.reproduction_json),
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


@router.get("/{evidence_id}/rows")
def get_evidence_rows(
    evidence_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get source rows backing this evidence, limited to 200 rows with explorer URLs."""
    ev = session.get(Evidence, evidence_id)
    if not ev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Evidence {evidence_id} not found"}},
        )

    ses = session.get(AnalysisSession, ev.session_id)
    if not ses or ses.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Evidence {evidence_id} not found"}},
        )

    spec_dict = json.loads(ev.spec_json)
    spec = AnalysisSpec.model_validate(spec_dict)

    # Find parquet path
    version = session.get(DatasetVersion, spec.dataset_version_id)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Dataset version not found"}},
        )

    # Read slice with DuckDB backend
    backend = LocalBackend()
    table_map = {"main": version.parquet_path}

    metric_pack = load_metric_pack("treasury_v1")
    sql, params = compile_spec(spec, metric_pack)

    paged_sql = f"{sql} LIMIT {limit} OFFSET {offset}"
    try:
        query_res = backend.execute_query(paged_sql, params, table_map)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "EXECUTION_ERROR", "message": str(exc)}},
        ) from exc

    rows: list[dict[str, Any]] = []
    cols = query_res.columns
    for r in query_res.rows:
        row_dict = {col: val for col, val in zip(cols, r)}
        if "tx_signature" in row_dict and row_dict["tx_signature"]:
            sig = str(row_dict["tx_signature"])
            row_dict["explorer_url"] = f"https://explorer.solana.com/tx/{sig}?cluster=devnet"
        rows.append(row_dict)

    return {
        "evidence_id": evidence_id,
        "offset": offset,
        "limit": limit,
        "total_rows": len(rows),
        "rows": rows,
    }


@router.post("/{evidence_id}/prove")
def prove_evidence(
    evidence_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Deterministically re-run the evidence reproduction query in an isolated connection."""
    ev = session.get(Evidence, evidence_id)
    if not ev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Evidence {evidence_id} not found"}},
        )

    ses = session.get(AnalysisSession, ev.session_id)
    if not ses or ses.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Evidence {evidence_id} not found"}},
        )

    repro = json.loads(ev.reproduction_json)
    sql = repro.get("query")
    params = repro.get("params", [])
    spec_dict = json.loads(ev.spec_json)
    spec = AnalysisSpec.model_validate(spec_dict)

    version = session.get(DatasetVersion, spec.dataset_version_id)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Dataset version not found"}},
        )

    backend = LocalBackend()
    table_map = {"main": version.parquet_path}

    try:
        query_res = backend.execute_query(sql, params, table_map)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "REPRODUCTION_FAILED", "message": str(exc)}},
        ) from exc

    computed_result_hash = hash_obj(query_res.to_dict())
    matches = (computed_result_hash == ev.result_hash)

    return {
        "evidence_id": evidence_id,
        "matches": matches,
        "result_hash": computed_result_hash,
        "expected_hash": ev.result_hash,
    }
