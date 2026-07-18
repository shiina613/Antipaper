"""Shared OpenAI-compatible structured-output client for backend AI stages."""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel


ResponseT = TypeVar("ResponseT", bound=BaseModel)


class LLMClientError(RuntimeError):
    """Raised when the configured model cannot return valid structured output."""


def _extract_json_content(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


class OpenAICompatibleLLMClient:
    """Small async client shared by report generation and grounded Q&A."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 45.0,
        max_retries: int = 1,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        if self.base_url.endswith("/chat/completions"):
            self.base_url = self.base_url[: -len("/chat/completions")]
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)

    async def __call__(
        self,
        messages: list[dict[str, str]],
        response_model: type[ResponseT],
    ) -> ResponseT:
        schema = json.dumps(
            response_model.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        request_messages = [dict(message) for message in messages]
        request_messages.append(
            {
                "role": "system",
                "content": (
                    "JSON trả về phải tuân thủ chính xác JSON Schema sau; không đổi tên "
                    f"field và không thêm văn bản ngoài JSON: {schema}"
                ),
            }
        )
        payload = {
            "model": self.model,
            "messages": request_messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: BaseException | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                return response_model.model_validate(_extract_json_content(content))
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code >= 500
                if attempt >= self.max_retries or not retryable:
                    break
                await asyncio.sleep(0.5 * (2**attempt))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise LLMClientError("Model returned invalid structured output") from exc
        raise LLMClientError("Model request failed after configured retries") from last_error


def build_shared_llm_client() -> OpenAICompatibleLLMClient | None:
    """Return the configured client, or ``None`` for explicit heuristic fallback."""

    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    if not api_key or not model:
        return None
    base_url = os.getenv("LLM_BASE_URL", "").strip() or "https://api.openai.com/v1"
    return OpenAICompatibleLLMClient(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "45")),
        max_retries=int(os.getenv("LLM_MAX_RETRIES", "1")),
    )
