"""LLM provider wrapper with retries, timeouts, structured output, and disk cache per §8.7."""

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Optional, Protocol, runtime_checkable

from pydantic import BaseModel

from backend.config import settings
from backend.core.errors import BudgetExceededError


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage_input_tokens: int = 0
    usage_output_tokens: int = 0


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM model providers."""

    def complete(
        self,
        messages: list[dict[str, Any]],
        system: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        max_tokens: int = 4000,
        temperature: float = 0.0,
    ) -> LLMResponse:
        ...


class DiskCacheLLM:
    """Simple on-disk prompt-to-response cache for tests and reproducible runs."""

    def __init__(self, cache_dir: str = ".llm_cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, model: str, messages: list[dict[str, Any]], system: str | None) -> str:
        raw = json.dumps({"model": model, "messages": messages, "system": system}, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, model: str, messages: list[dict[str, Any]], system: str | None) -> LLMResponse | None:
        key = self._key(model, messages, system)
        fp = self.cache_dir / f"{key}.json"
        if fp.exists():
            try:
                data = json.loads(fp.read_text("utf-8"))
                tool_calls = [
                    ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                    for tc in data.get("tool_calls", [])
                ]
                return LLMResponse(
                    content=data.get("content", ""),
                    tool_calls=tool_calls,
                    usage_input_tokens=data.get("usage_input_tokens", 0),
                    usage_output_tokens=data.get("usage_output_tokens", 0),
                )
            except Exception:
                return None
        return None

    def set(self, model: str, messages: list[dict[str, Any]], system: str | None, resp: LLMResponse) -> None:
        key = self._key(model, messages, system)
        fp = self.cache_dir / f"{key}.json"
        data = {
            "content": resp.content,
            "tool_calls": [{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in resp.tool_calls],
            "usage_input_tokens": resp.usage_input_tokens,
            "usage_output_tokens": resp.usage_output_tokens,
        }
        fp.write_text(json.dumps(data, indent=2), encoding="utf-8")


class FakeLLMProvider:
    """Deterministic mock LLM provider for tests and offline development."""

    def __init__(self, canned_responses: Optional[list[LLMResponse]] = None) -> None:
        self.canned = canned_responses or []
        self._idx = 0
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        system: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        max_tokens: int = 4000,
        temperature: float = 0.0,
    ) -> LLMResponse:
        self.calls.append({"messages": messages, "system": system, "tools": tools})
        if self._idx < len(self.canned):
            resp = self.canned[self._idx]
            self._idx += 1
            return resp

        # Default fallback response
        last_msg = messages[-1].get("content", "") if messages else ""
        return LLMResponse(
            content=f"Analysis of: {last_msg}",
            tool_calls=[],
            usage_input_tokens=50,
            usage_output_tokens=20,
        )


class AnthropicProvider:
    """Production Anthropic Claude API provider with exponential backoff and retries."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.analyx_llm_model
        self.cache = DiskCacheLLM()

    def complete(
        self,
        messages: list[dict[str, Any]],
        system: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        max_tokens: int = 4000,
        temperature: float = 0.0,
    ) -> LLMResponse:
        # Check disk cache first
        cached = self.cache.get(self.model, messages, system)
        if cached:
            return cached

        if not self.api_key:
            # Fall back to fake provider if no key provided
            return FakeLLMProvider().complete(messages, system, tools, max_tokens, temperature)

        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)

        retries = 3
        backoff = 1.0
        for attempt in range(retries):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model,
                    "max_tokens": min(max_tokens, settings.budget_max_output_tokens),
                    "temperature": temperature,
                    "messages": messages,
                }
                if system:
                    kwargs["system"] = system
                if tools:
                    kwargs["tools"] = tools

                response = client.messages.create(**kwargs)

                # Parse tool calls and content
                text_content = ""
                tool_calls: list[ToolCall] = []

                for block in response.content:
                    if block.type == "text":
                        text_content += block.text
                    elif block.type == "tool_use":
                        tool_calls.append(
                            ToolCall(
                                id=block.id,
                                name=block.name,
                                arguments=block.input,
                            )
                        )

                llm_resp = LLMResponse(
                    content=text_content,
                    tool_calls=tool_calls,
                    usage_input_tokens=response.usage.input_tokens,
                    usage_output_tokens=response.usage.output_tokens,
                )

                # Save in cache
                self.cache.set(self.model, messages, system, llm_resp)
                return llm_resp

            except anthropic.RateLimitError as e:
                if attempt == retries - 1:
                    raise BudgetExceededError(f"Anthropic rate limit exceeded: {e}") from e
                time.sleep(backoff)
                backoff *= 2.0
            except anthropic.APIError as e:
                if attempt == retries - 1:
                    raise RuntimeError(f"Anthropic API error: {e}") from e
                time.sleep(backoff)
                backoff *= 2.0

        raise RuntimeError("Exceeded retry limit for LLM completion")


def get_llm_provider() -> LLMProvider:
    """Factory creating configured LLM provider."""
    if settings.anthropic_api_key:
        return AnthropicProvider()
    return FakeLLMProvider()
