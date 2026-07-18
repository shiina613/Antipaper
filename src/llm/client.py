"""OpenAI-compatible shared LLM client with schema validation."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


class LlmClientError(RuntimeError):
    """Base error for shared model-client failures."""


class LlmClientConfigurationError(LlmClientError):
    """Raised when required model configuration is missing."""


class LlmClientTimeoutError(LlmClientError):
    """Raised when all retry attempts time out."""


@dataclass(frozen=True)
class LlmSettings:
    """Configuration loaded from environment by default."""

    api_url: str
    api_key: str | None = None
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 30.0
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "LlmSettings":
        api_url = os.getenv("LLM_API_URL", "").strip()
        if not api_url:
            raise LlmClientConfigurationError("Missing LLM_API_URL.")

        return cls(
            api_url=api_url,
            api_key=os.getenv("LLM_API_KEY"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
        )


class LlmClient:
    """Minimal OpenAI-compatible client used by intelligence builders."""

    def __init__(
        self,
        settings: LlmSettings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or LlmSettings.from_env()
        self._client = http_client

    async def call(
        self,
        messages: list[dict[str, Any]],
        response_model: type[T],
    ) -> T:
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"

        attempts = max(self.settings.max_retries, 0) + 1
        last_timeout: httpx.TimeoutException | None = None
        for _ in range(attempts):
            try:
                response = await self._post(payload=payload, headers=headers)
                response.raise_for_status()
                return self._parse_response(response.json(), response_model)
            except httpx.TimeoutException as exc:
                last_timeout = exc
                continue
            except ValidationError as exc:
                raise LlmClientError(f"LLM response failed schema validation: {exc}") from exc
            except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError) as exc:
                raise LlmClientError(f"LLM request failed: {exc}") from exc

        raise LlmClientTimeoutError("LLM request timed out after retries.") from last_timeout

    async def _post(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        if self._client is not None:
            return await self._client.post(
                self.settings.api_url,
                json=payload,
                headers=headers,
                timeout=self.settings.timeout_seconds,
            )

        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            return await client.post(
                self.settings.api_url,
                json=payload,
                headers=headers,
            )

    @staticmethod
    def _parse_response(payload: dict[str, Any], response_model: type[T]) -> T:
        content: Any
        if "choices" in payload:
            content = payload["choices"][0]["message"]["content"]
        else:
            content = payload

        if isinstance(content, str):
            content = json.loads(content)
        return response_model.model_validate(content)


async def call_llm(
    messages: list[dict[str, Any]],
    response_model: type[T],
) -> T:
    return await LlmClient().call(messages, response_model)
