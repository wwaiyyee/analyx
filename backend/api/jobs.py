"""Background job tracking endpoints."""

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from backend.api.auth import get_current_workspace
from backend.db.models import Job, Workspace
from backend.db.session import get_session

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobResponse(BaseModel):
    id: str
    kind: str
    status: str
    progress: float  # 0.0 to 1.0
    dataset_id: Optional[str] = None
    message: Optional[str] = None
    result: Optional[dict[str, Any]] = None


@router.get("/{job_id}", response_model=JobResponse)
def get_job_status(
    job_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> JobResponse:
    """Retrieve asynchronous background job status, progress, and result."""
    job = session.get(Job, job_id)
    if not job or (job.workspace_id and job.workspace_id != workspace.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Job {job_id} not found"}},
        )

    res_data: Optional[dict[str, Any]] = None
    dataset_id: Optional[str] = None
    if job.result_json:
        try:
            res_data = json.loads(job.result_json)
            if isinstance(res_data, dict):
                dataset_id = res_data.get("dataset_id")
        except Exception:
            pass

    # Normalize progress to 0.0 - 1.0 scale
    norm_progress = min(max(float(job.progress) / 100.0, 0.0), 1.0)

    # Normalize status string if "completed" -> "done"
    norm_status = "done" if job.status == "completed" else job.status

    return JobResponse(
        id=job.id,
        kind=job.kind,
        status=norm_status,
        progress=norm_progress,
        dataset_id=dataset_id,
        message=job.error,
        result=res_data,
    )
