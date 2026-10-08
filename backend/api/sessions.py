"""Analysis session and chat streaming endpoints."""

from datetime import datetime, timezone
import json
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.api.auth import get_current_workspace
from backend.core.ids import generate_id
from backend.db.models import AnalysisSession, Assumption, DatasetVersion, Finding, Workspace
from backend.db.session import get_session

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field(default="New Analysis", description="Session title")
    dataset_ids: Optional[list[str]] = Field(default=None, description="Datasets involved")


class MessageRequest(BaseModel):
    text: str = Field(..., description="User message or query")


class AnswerRequest(BaseModel):
    question_id: str = Field(..., description="ID of question card being answered")
    choice: str = Field(..., description="Selected option or freeform text")


@router.post("")
def create_session(
    req: CreateSessionRequest,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create a new conversational analysis session."""
    anchor_dt: Optional[datetime] = None
    if req.dataset_ids:
        # Find latest time_anchor from specified datasets
        stmt = (
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id.in_(req.dataset_ids))  # type: ignore
            .order_by(DatasetVersion.created_at.desc())
        )
        v = session.exec(stmt).first()
        if v and v.time_anchor:
            anchor_dt = v.time_anchor

    new_session = AnalysisSession(
        workspace_id=workspace.id,
        title=req.title or "New Analysis",
        time_anchor=anchor_dt,
        messages_json="[]",
    )
    session.add(new_session)
    session.commit()
    session.refresh(new_session)

    return new_session.model_dump()


@router.get("/{session_id}")
def get_session_detail(
    session_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get analysis session with its messages, findings, and assumptions."""
    ses = session.get(AnalysisSession, session_id)
    if not ses or ses.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Session {session_id} not found"}},
        )

    # Findings
    f_stmt = select(Finding).where(Finding.session_id == session_id)
    findings = session.exec(f_stmt).all()

    # Assumptions
    a_stmt = select(Assumption).where(Assumption.session_id == session_id)
    assumptions = session.exec(a_stmt).all()

    try:
        messages = json.loads(ses.messages_json)
    except Exception:
        messages = []

    return {
        "session": ses.model_dump(),
        "messages": messages,
        "findings": [f.model_dump() for f in findings],
        "assumptions": [a.model_dump() for a in assumptions],
    }


from backend.agent.orchestrator import run_orchestrator


async def _stream_chat_response(
    session_id: str,
    user_text: str,
    workspace_id: str,
    session_db: Session,
) -> AsyncGenerator[str, None]:
    """Generate Server-Sent Events (SSE) for agent processing steps via orchestrator."""
    async for event in run_orchestrator(
        session_id=session_id,
        user_query=user_text,
        workspace_id=workspace_id,
        db_session=session_db,
    ):
        yield event.to_sse()


@router.post("/{session_id}/messages")
async def post_message(
    session_id: str,
    req: MessageRequest,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Post user message and stream agent reasoning, findings, and answer via SSE."""
    ses = session.get(AnalysisSession, session_id)
    if not ses or ses.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Session {session_id} not found"}},
        )

    # Append user message to session history
    try:
        messages = json.loads(ses.messages_json)
    except Exception:
        messages = []

    user_msg = {
        "id": generate_id("msg"),
        "role": "user",
        "content": req.text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    messages.append(user_msg)
    ses.messages_json = json.dumps(messages)
    ses.updated_at = datetime.now(timezone.utc)
    session.add(ses)
    session.commit()

    return StreamingResponse(
        _stream_chat_response(session_id, req.text, workspace.id, session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{session_id}/answers")
def answer_question_card(
    session_id: str,
    req: AnswerRequest,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Submit answer to a question card or clarify an assumption."""
    ses = session.get(AnalysisSession, session_id)
    if not ses or ses.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Session {session_id} not found"}},
        )

    # Track assumption or answer in session history
    try:
        messages = json.loads(ses.messages_json)
    except Exception:
        messages = []

    answer_msg = {
        "id": generate_id("msg"),
        "role": "user",
        "question_id": req.question_id,
        "content": f"[Answer to {req.question_id}]: {req.choice}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    messages.append(answer_msg)
    ses.messages_json = json.dumps(messages)
    session.add(ses)
    session.commit()

    return {
        "session_id": session_id,
        "question_id": req.question_id,
        "choice": req.choice,
        "status": "recorded",
    }
