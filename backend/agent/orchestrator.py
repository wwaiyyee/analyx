"""Agent orchestrator loop coordinating routing, planning, tool execution, and answer composition per §8.7."""

from datetime import datetime, timezone
import json
from typing import Any, AsyncGenerator, Optional

from sqlmodel import Session, select

from backend.agent.composer import compose_answer
from backend.agent.events import (
    AgentEvent,
    answer_delta_event,
    done_event,
    error_event,
    finding_event,
    plan_event,
    question_cards_event,
    status_event,
)
from backend.agent.llm import LLMProvider, get_llm_provider
from backend.agent.prompts import ANALYST_SYSTEM_PROMPT, sanitize_input_prompt
from backend.agent.router import route_request
from backend.agent.tools import TOOL_DEFINITIONS, ToolExecutor
from backend.core.errors import BudgetExceededError
from backend.db.models import AnalysisSession, Dataset, DatasetVersion, Evidence, Finding


async def run_orchestrator(
    session_id: str,
    user_query: str,
    workspace_id: str,
    db_session: Session,
    provider: Optional[LLMProvider] = None,
) -> AsyncGenerator[AgentEvent, None]:
    """Execute autonomous agent loop emitting structured SSE events."""
    p = provider or get_llm_provider()
    executor = ToolExecutor(workspace_id=workspace_id, session_id=session_id, db_session=db_session)

    # 1. Routing
    yield status_event("Classifying request and evaluating computational requirements...")
    route = route_request(user_query, provider=p)
    tier = route.tier
    budget = route.budget

    # 2. Plan
    plan_steps = [
        f"Route request (Tier: {tier}, Budget: {budget} tool calls)",
        "Inspect workspace datasets and semantic dictionary",
        "Verify sufficiency and compile deterministic AnalysisSpec",
        "Execute engine query and construct cryptographic evidence",
        "Validate claims against number and language grounding rules",
        "Compose verified answer with metric placeholders",
    ]
    yield plan_event(plan_steps)

    if route.needs_clarification:
        yield question_cards_event([
            {
                "id": "clarify_window",
                "question": "Which time window should be analyzed?",
                "choices": ["Last complete month", "Quarter-to-date", "Full history"],
            }
        ])
        yield done_event(session_id=session_id, tool_calls_used=0)
        return

    # 3. Setup conversation context with dynamic workspace dataset schemas
    from backend.db.models import DataDictionaryEntry
    ds_stmt = select(Dataset).where(Dataset.workspace_id == workspace_id)
    ws_datasets = db_session.exec(ds_stmt).all()
    ds_context_lines = []
    for d in ws_datasets:
        v_stmt = select(DatasetVersion).where(DatasetVersion.dataset_id == d.id).order_by(DatasetVersion.version_num.desc())
        v = db_session.exec(v_stmt).first()
        if v:
            dict_stmt = select(DataDictionaryEntry).where(DataDictionaryEntry.dataset_id == d.id)
            entries = db_session.exec(dict_stmt).all()
            col_desc = ", ".join([f"{e.column_name} ({e.role})" for e in entries[:15]])
            ds_context_lines.append(f"- Dataset '{d.name}' (id: '{d.id}', version_id: '{v.id}', {v.row_count} rows): Columns: {col_desc}")

    dynamic_system = ANALYST_SYSTEM_PROMPT
    if ds_context_lines:
        dynamic_system += "\n\nAvailable Workspace Datasets:\n" + "\n".join(ds_context_lines)

    sanitized_query = sanitize_input_prompt(user_query)
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": f"<data>{sanitized_query}</data>"}
    ]

    tool_calls_used = 0
    evidence_map: dict[str, Any] = {}
    validated_findings: list[dict[str, Any]] = []

    # 4. Agent Tool Use Loop
    while tool_calls_used < budget:
        yield status_event(f"Executing analytical loop (Step {tool_calls_used + 1}/{budget})...")

        try:
            llm_resp = p.complete(
                messages=messages,
                system=dynamic_system,
                tools=TOOL_DEFINITIONS,
                max_tokens=2000,
            )
        except BudgetExceededError as exc:
            yield status_event(f"Budget limit reached: {exc}")
            break
        except Exception as exc:
            yield error_event("AGENT_ERROR", f"LLM error: {exc}")
            break

        # Check for tool calls
        if not llm_resp.tool_calls:
            # Agent finished calling tools
            break

        # Append assistant response to history
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": llm_resp.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in llm_resp.tool_calls
            ],
        }
        messages.append(assistant_msg)

        # Execute each tool call
        for tc in llm_resp.tool_calls:
            tool_calls_used += 1
            yield status_event(f"Executing tool: {tc.name}...")

            tool_result = executor.execute(tc.name, tc.arguments)

            # Track evidence and findings
            if tc.name == "run_analysis" and "evidence_id" in tool_result:
                ev_id = tool_result["evidence_id"]
                evidence_map[ev_id] = tool_result

            elif tc.name == "propose_finding" and "finding_id" in tool_result:
                validated_findings.append(tool_result)
                yield finding_event(tool_result)

            elif tc.name == "ask_user" and "questions" in tool_result:
                yield question_cards_event(tool_result["questions"])
                yield done_event(session_id=session_id, tool_calls_used=tool_calls_used)
                return

            # Append tool result to context (strictly JSON summary, NO raw rows)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.name,
                "content": json.dumps(tool_result),
            })

            if tool_calls_used >= budget:
                yield status_event(
                    f"Reached maximum tool call budget of {budget}. Halting loop and composing answer."
                )
                break

    # 5. Build findings from evidence if none was directly returned
    if not validated_findings:
        from backend.core.ids import generate_id
        if evidence_map:
            for ev_id, ev_data in evidence_map.items():
                metrics = ev_data.get("metrics", {})
                for m_name, m_val in metrics.items():
                    claim_str = f"Calculated {m_name.replace('_', ' ')}: {m_val}."
                    finding = Finding(
                        id=generate_id("fd"),
                        session_id=session_id,
                        evidence_id=ev_id,
                        claim=claim_str,
                        claim_type="metric",
                        status="supported",
                    )
                    db_session.add(finding)
                    db_session.commit()
                    db_session.refresh(finding)
                    f_dict = finding.model_dump()
                    validated_findings.append(f_dict)
                    yield finding_event(f_dict)

        if not validated_findings:
            f_stmt = select(Finding).where(Finding.session_id == session_id)
            findings_in_db = db_session.exec(f_stmt).all()
            for f in findings_in_db:
                validated_findings.append(f.model_dump())
                ev = db_session.get(Evidence, f.evidence_id)
                if ev and ev.id not in evidence_map:
                    evidence_map[ev.id] = {
                        "evidence_id": ev.id,
                        "metrics": json.loads(ev.metrics_json),
                    }

    # 6. Compose Answer
    yield status_event("Composing grounded answer...")
    final_answer = compose_answer(
        findings=validated_findings,
        evidence_map=evidence_map,
        user_query=user_query,
        provider=p,
    )

    # Stream answer delta
    yield answer_delta_event(final_answer)

    # Done
    yield done_event(session_id=session_id, tool_calls_used=tool_calls_used)
