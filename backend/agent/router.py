"""Request router classifying queries into execution tiers per §8.7."""

from dataclasses import dataclass
import json
import re
from typing import Literal, Optional

from backend.agent.llm import LLMProvider, get_llm_provider
from backend.agent.prompts import ROUTER_SYSTEM_PROMPT, sanitize_input_prompt
from backend.config import settings

TierType = Literal["lookup", "analysis", "investigation", "report"]


@dataclass
class RouterResult:
    tier: TierType
    needs_clarification: bool
    budget: int  # Max tool call allowance


def _keyword_route(text: str) -> RouterResult:
    """Deterministic fallback routing using keyword analysis."""
    lowered = text.lower()

    if any(k in lowered for k in ["generate report", "create report", "build report", "full report", "summary report"]):
        return RouterResult(
            tier="report",
            needs_clarification=False,
            budget=settings.budget_investigation_tool_calls,
        )

    if any(k in lowered for k in ["why", "what changed", "spike", "driver", "driven by", "investigate", "cause", "anomaly", "root cause"]):
        return RouterResult(
            tier="investigation",
            needs_clarification=False,
            budget=settings.budget_investigation_tool_calls,
        )

    if any(k in lowered for k in ["compare", "month-over-month", "month over month", "mom", "trend", "breakdown", "distribution", "runway", "top-5", "top 5"]):
        return RouterResult(
            tier="analysis",
            needs_clarification=False,
            budget=settings.budget_analysis_tool_calls,
        )

    # Default to fast lookup
    return RouterResult(
        tier="lookup",
        needs_clarification=False,
        budget=settings.budget_lookup_tool_calls,
    )


def route_request(
    text: str,
    provider: Optional[LLMProvider] = None,
) -> RouterResult:
    """Classify user request into execution tier with budget allocation."""
    p = provider or get_llm_provider()

    sanitized = sanitize_input_prompt(text)
    messages = [{"role": "user", "content": f"<data>{sanitized}</data>"}]

    try:
        resp = p.complete(
            messages=messages,
            system=ROUTER_SYSTEM_PROMPT,
            max_tokens=100,
            temperature=0.0,
        )

        # Parse JSON
        content = resp.content.strip()
        # Find JSON block if wrapped
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            raw_tier = data.get("tier", "lookup").lower()
            needs_clarification = bool(data.get("needs_clarification", False))

            if raw_tier in ("lookup", "analysis", "investigation", "report"):
                tier: TierType = raw_tier  # type: ignore
                budget_map = {
                    "lookup": settings.budget_lookup_tool_calls,
                    "analysis": settings.budget_analysis_tool_calls,
                    "investigation": settings.budget_investigation_tool_calls,
                    "report": settings.budget_investigation_tool_calls,
                }
                return RouterResult(
                    tier=tier,
                    needs_clarification=needs_clarification,
                    budget=budget_map[tier],
                )
    except Exception:
        pass

    # Fall back to deterministic keyword routing
    return _keyword_route(text)
