"""One bounded OpenAI-compatible structured-output client."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class LlmClientError(RuntimeError):
    """Raised when a structured LLM request fails."""


class LlmClientConfigurationError(LlmClientError):
    """Raised when the LLM environment is incomplete."""


class LlmClientTimeoutError(LlmClientError):
    """Raised when the LLM exceeds its bounded request timeout."""


class LlmClientOutputError(LlmClientError):
    """Raised when a model response cannot be decoded into the requested contract."""


@dataclass(frozen=True)
class LlmSettings:
    api_url: str
    api_key: str | None
    model: str
    timeout_seconds: float = 10.0
    max_retries: int = 0
    max_output_tokens: int = 800

    @classmethod
    def from_env(cls) -> "LlmSettings":
        base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        configured_url = os.getenv("LLM_API_URL", "").strip()
        api_url = configured_url or (
            base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        )
        return cls(
            api_url=api_url,
            api_key=os.getenv("LLM_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip() or None,
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "10")),
            max_retries=max(0, min(2, int(os.getenv("LLM_MAX_RETRIES", "1")))),
            max_output_tokens=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1600")),
        )


class LlmClient:
    def __init__(self, settings: LlmSettings | None = None) -> None:
        self.settings = settings or LlmSettings.from_env()
        if not self.settings.api_key:
            raise LlmClientConfigurationError("LLM_API_KEY or OPENAI_API_KEY is required.")

    async def call(self, messages: list[dict[str, Any]], response_model: type[T]) -> T:
        schema_message = {
            "role": "system",
            "content": (
                "Return exactly one JSON object, without Markdown or explanatory text. "
                "The response format enforces the required JSON Schema."
            ),
        }
        payload = {
            "model": self.settings.model,
            "messages": [schema_message, *messages],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__.lower(),
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            },
            "max_completion_tokens": self.settings.max_output_tokens,
        }
        for attempt in range(self.settings.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                    response = await client.post(
                        self.settings.api_url,
                        json=payload,
                        headers={"Authorization": f"Bearer {self.settings.api_key}"},
                    )
                response.raise_for_status()
                return self._validate_response(response.json(), response_model)
            except LlmClientOutputError as exc:
                if attempt >= self.settings.max_retries:
                    raise
                logger.warning(
                    "llm_structured_output_invalid model=%s schema=%s attempt=%d/%d reason=%s",
                    self.settings.model,
                    response_model.__name__,
                    attempt + 1,
                    self.settings.max_retries + 1,
                    str(exc),
                )
                payload["messages"] = [
                    *payload["messages"],
                    {
                        "role": "system",
                        "content": "Your previous response did not validate. Return the complete JSON object that exactly matches the schema. Do not truncate the response.",
                    },
                ]
            except httpx.TimeoutException as exc:
                raise LlmClientTimeoutError("LLM request timed out.") from exc
            except httpx.HTTPStatusError as exc:
                detail = ""
                try:
                    detail = str(exc.response.json().get("error", {}).get("message", "")).strip()
                except (TypeError, ValueError):
                    pass
                message = f"LLM request failed with HTTP {exc.response.status_code}."
                if detail:
                    message += f" {detail}"
                raise LlmClientError(message) from exc
            except httpx.HTTPError as exc:
                raise LlmClientError("LLM request failed before a valid response was received.") from exc
        raise AssertionError("unreachable")

    @staticmethod
    def _validate_response(payload: Any, response_model: type[T]) -> T:
        """Decode compatible chat-completions payloads without exposing model text."""

        try:
            choice = payload["choices"][0]
            if choice.get("finish_reason") == "length":
                raise LlmClientOutputError("Model output was truncated by its token limit.")
            message = choice["message"]
            refusal = message.get("refusal")
            if refusal:
                raise LlmClientOutputError("Model refused the structured-output request.")
            content = message["content"]
            decoded = LlmClient._decode_json_content(content)
            return response_model.model_validate(decoded)
        except LlmClientOutputError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            raise LlmClientOutputError(
                "LLM response is not valid JSON matching the requested schema."
            ) from exc

    @staticmethod
    def _decode_json_content(content: Any) -> Any:
        if not isinstance(content, str):
            return content
        text = content.strip()
        if text.startswith("```") and text.endswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        decoder = json.JSONDecoder()
        value, offset = decoder.raw_decode(text)
        if text[offset:].strip():
            raise json.JSONDecodeError("unexpected data after JSON value", text, offset)
        return value


async def call_llm(messages: list[dict[str, Any]], response_model: type[T]) -> T:
    return await LlmClient().call(messages, response_model)
