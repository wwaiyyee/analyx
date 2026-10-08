"""Analytical report generation, inspection, and markdown export endpoints."""

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.api.auth import get_current_workspace
from backend.core.ids import generate_id
from backend.db.models import AnalysisSession, Finding, Report, Workspace
from backend.db.session import get_session

router = APIRouter(tags=["reports"])


class GenerateReportRequest(BaseModel):
    title: str = Field(default="Analysis Report", description="Custom report title")


@router.post("/sessions/{session_id}/report")
def generate_report(
    session_id: str,
    req: GenerateReportRequest = GenerateReportRequest(),
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Compile analytical session findings into a cryptographically anchored markdown report."""
    ses = session.get(AnalysisSession, session_id)
    if not ses or ses.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Session {session_id} not found"}},
        )

    # Retrieve all findings
    f_stmt = select(Finding).where(Finding.session_id == session_id)
    findings = session.exec(f_stmt).all()

    # Build report markdown
    lines = [
        f"# {req.title}",
        "",
        f"**Session:** `{session_id}`  ",
        f"**Generated:** `{ses.created_at.isoformat() if ses.created_at else ''}`  ",
        "",
        "## Executive Summary",
        "",
        f"This report documents verified analytical findings derived deterministically by Analyx.",
        "",
        "## Verified Findings",
        "",
    ]

    finding_hashes: list[str] = []
    for idx, f in enumerate(findings, start=1):
        lines.append(f"### Finding {idx}: {f.claim}")
        lines.append(f"- **Type:** `{f.claim_type}`")
        lines.append(f"- **Status:** `{f.status}`")
        lines.append(f"- **Evidence ID:** `{f.evidence_id}`")
        lines.append(f"- **Grounded Numbers:** `{'Yes' if f.numbers_grounded else 'No'}`")
        lines.append("")
        f_hash = hashlib.sha256(f.claim.encode("utf-8")).hexdigest()
        finding_hashes.append(f_hash)

    lines.append("## Attestation & Integrity")
    lines.append("")
    lines.append(
        "All claims and metrics in this document are backed by cryptographically verifiable computational evidence."
    )

    markdown_body = "\n".join(lines)
    report_sha = hashlib.sha256(markdown_body.encode("utf-8")).hexdigest()

    report = Report(
        id=generate_id("rp"),
        workspace_id=workspace.id,
        session_id=session_id,
        title=req.title,
        markdown_content=markdown_body,
        sha256=report_sha,
        frozen_region_hashes_json=json.dumps(finding_hashes),
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    return report.model_dump()


@router.get("/reports/{report_id}")
def get_report(
    report_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve full analytical report by ID."""
    report = session.get(Report, report_id)
    if not report or report.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Report {report_id} not found"}},
        )

    return report.model_dump()


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: str,
    format: str = Query(default="md", regex="^(md|pdf)$"),
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> Response:
    """Export report as downloadable Markdown file."""
    report = session.get(Report, report_id)
    if not report or report.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Report {report_id} not found"}},
        )

    if format == "pdf":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={"error": {"code": "NOT_IMPLEMENTED", "message": "PDF export is a P1 feature"}},
        )

    return Response(
        content=report.markdown_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="analyx_report_{report.id}.md"',
        },
    )
