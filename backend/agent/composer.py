"""Answer composer turning validated findings into grounded plain language per §8.7."""

from decimal import Decimal
import re
from typing import Any, Optional

from backend.agent.llm import LLMProvider, get_llm_provider
from backend.agent.prompts import COMPOSER_SYSTEM_PROMPT
from backend.validate.language_lint import lint_language
from backend.validate.number_lint import lint_numbers


def format_metric_value(key: str, value: Any) -> str:
    """Format raw decimal string metric with proper currency/unit decoration."""
    try:
        val_str = str(value).strip()
        dec = Decimal(val_str)
    except Exception:
        return str(value)

    low_key = key.lower()
    # Currency
    if any(k in low_key for k in ("usd", "dollar", "revenue", "price", "outflow", "inflow", "burn", "balance", "cost")):
        return f"${dec:,.2f}"

    # Percentage
    if any(k in low_key for k in ("pct", "percent", "ratio", "rate")):
        pct_val = dec * 100 if dec <= 1 and dec >= -1 else dec
        return f"{pct_val:.1f}%"

    # Integer counts
    if any(k in low_key for k in ("count", "txs", "transactions", "counterparties", "slot")):
        return f"{int(dec):,}"

    # Generic decimal
    if "." in val_str:
        return f"{dec:,.2f}"
    return f"{int(dec):,}"


def substitute_metric_placeholders(text: str, evidence_map: dict[str, dict[str, Any]]) -> str:
    """Substitute {{metric:<ev_id>.<key>}} or {{metric:<key>}} placeholders with formatted values."""
    # Collect flat metrics map as fallback
    flat_metrics: dict[str, Any] = {}
    for ev_id, ev_data in evidence_map.items():
        metrics = ev_data.get("metrics", {})
        flat_metrics.update(metrics)

    def _replace(match: re.Match[str]) -> str:
        ref = match.group(1).strip()
        if "." in ref:
            ev_id, key = ref.split(".", 1)
            ev_data = evidence_map.get(ev_id, {})
            metrics = ev_data.get("metrics", {})
            if key in metrics:
                return format_metric_value(key, metrics[key])
        if ref in flat_metrics:
            return format_metric_value(ref, flat_metrics[ref])
        return match.group(0)

    # Replace {{metric:...}}
    return re.sub(r"\{\{metric:([^}]+)\}\}", _replace, text)


def render_deterministic_answer(findings: list[dict[str, Any]], evidence_map: dict[str, Any]) -> str:
    """Deterministic fallback answer assembled entirely from validated findings without LLM generation."""
    if not findings:
        return "No verifiable findings could be established from the dataset."

    paragraphs: list[str] = []
    for f in findings:
        claim = f.get("claim", "")
        ev_id = f.get("evidence_id", "")
        status = f.get("status", "supported")
        ev_info = evidence_map.get(ev_id, {})
        metrics = ev_info.get("metrics", {})

        # Build clean grounded sentence
        if metrics:
            formatted_items = [f"{k}: {format_metric_value(k, v)}" for k, v in metrics.items()]
            summary_metrics = ", ".join(formatted_items)
            p = f"{claim} (Verified: {summary_metrics}; Status: {status})."
        else:
            p = f"{claim} (Status: {status})."
        paragraphs.append(p)

    paragraphs.append(
        "All calculations were executed deterministically by the Analyx engine with cryptographic evidence verification."
    )
    return "\n\n".join(paragraphs)


def compose_answer(
    findings: list[dict[str, Any]],
    evidence_map: dict[str, Any],
    user_query: str,
    provider: Optional[LLMProvider] = None,
) -> str:
    """Compose natural language answer, validating against number grounding and language lints."""
    if not findings:
        return "No sufficient evidence found to answer the query."

    # Flat metrics for number lint verification
    all_metrics: dict[str, Any] = {}
    for ev_info in evidence_map.values():
        all_metrics.update(ev_info.get("metrics", {}))

    p = provider or get_llm_provider()

    # Try LLM composition
    findings_str = "\n".join([f"- {f.get('claim', '')} (Evidence ID: {f.get('evidence_id', '')})" for f in findings])
    user_prompt = (
        f"User query: {user_query}\n\n"
        f"Validated findings:\n{findings_str}\n\n"
        f"Available evidence metrics:\n{all_metrics}\n\n"
        "Compose the final concise answer. Use {{metric:<ev_id>.<key>}} placeholders."
    )

    messages = [{"role": "user", "content": user_prompt}]

    for attempt in range(2):
        try:
            resp = p.complete(messages=messages, system=COMPOSER_SYSTEM_PROMPT, max_tokens=1000)
            composed_text = resp.content.strip()

            # Substitute metric placeholders
            hydrated_text = substitute_metric_placeholders(composed_text, evidence_map)

            # Validate
            num_lint = lint_numbers(hydrated_text, all_metrics)
            lang_lint = lint_language(hydrated_text)

            if num_lint.passed and lang_lint.passed:
                return hydrated_text

            # If failed, retry with feedback
            messages.append({"role": "assistant", "content": composed_text})
            issues = []
            if not num_lint.passed:
                issues.append(f"Ungrounded numbers detected: {num_lint.ungrounded_tokens}. Use only metrics from evidence.")
            if not lang_lint.passed:
                issues.append(f"Causal language detected: {lang_lint.flagged_phrases}. Use associative phrasing.")
            messages.append({"role": "user", "content": f"Correction required: {' '.join(issues)}"})

        except Exception:
            break

    # If LLM composition fails twice or errors, fall back to deterministic template answer
    return render_deterministic_answer(findings, evidence_map)
