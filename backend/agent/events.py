"""Server-Sent Event (SSE) definitions and formatting per §8.7 and §9.3."""

from dataclasses import dataclass
import json
from typing import Any, Literal

SSEEventType = Literal[
    "status",
    "plan",
    "question_cards",
    "finding",
    "chart",
    "answer_delta",
    "assumption",
    "done",
    "error",
]


@dataclass
class AgentEvent:
    type: SSEEventType
    data: dict[str, Any]

    def to_sse(self) -> str:
        """Serialize event to standard SSE event line format."""
        payload = json.dumps({"type": self.type, "data": self.data})
        return f"data: {payload}\n\n"


def status_event(text: str) -> AgentEvent:
    """Short activity status update (never raw model chain-of-thought)."""
    return AgentEvent(type="status", data={"text": text})


def plan_event(steps: list[str]) -> AgentEvent:
    """Analytical execution plan."""
    return AgentEvent(type="plan", data={"steps": steps})


def finding_event(finding: dict[str, Any]) -> AgentEvent:
    """Validated analytical finding backed by evidence."""
    return AgentEvent(type="finding", data={"finding": finding})


def chart_event(chart: dict[str, Any]) -> AgentEvent:
    """Visualization chart specification."""
    return AgentEvent(type="chart", data={"chart": chart})


def answer_delta_event(delta: str) -> AgentEvent:
    """Streamed text chunk of composed answer."""
    return AgentEvent(type="answer_delta", data={"delta": delta})


def question_cards_event(questions: list[dict[str, Any]]) -> AgentEvent:
    """Interactive question cards for user clarification."""
    return AgentEvent(type="question_cards", data={"questions": questions})


def assumption_event(assumption: dict[str, Any]) -> AgentEvent:
    """Disclosed assumption affecting analysis."""
    return AgentEvent(type="assumption", data={"assumption": assumption})


def done_event(session_id: str, tool_calls_used: int) -> AgentEvent:
    """Analysis turn completion marker."""
    return AgentEvent(type="done", data={"session_id": session_id, "tool_calls_used": tool_calls_used})


def error_event(code: str, message: str) -> AgentEvent:
    """Error event."""
    return AgentEvent(type="error", data={"code": code, "message": message})
