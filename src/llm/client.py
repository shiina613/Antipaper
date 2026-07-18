"""OpenAI-compatible shared LLM client with schema validation."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import asyncio
import math
import threading
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)
EMBEDDING_API_URL = "https://api.openai.com/v1/embeddings"


class SharedAsyncLimiter:
    """Process-wide non-blocking limiter safe across event loops."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._semaphore = threading.BoundedSemaphore(capacity)

    async def __aenter__(self):
        while not self._semaphore.acquire(blocking=False):
            await asyncio.sleep(0.001)
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self._semaphore.release()


_SHARED_LIMITER: SharedAsyncLimiter | None = None
_SHARED_CAPACITY: int | None = None
_LIMITERS_LOCK = threading.Lock()


def shared_limiter(capacity: int) -> SharedAsyncLimiter:
    global _SHARED_LIMITER, _SHARED_CAPACITY
    with _LIMITERS_LOCK:
        if capacity <= 0:
            raise LlmClientConfigurationError("MAX_LLM_CONCURRENCY must be positive.")
        if _SHARED_LIMITER is None:
            _SHARED_CAPACITY = capacity
            _SHARED_LIMITER = SharedAsyncLimiter(capacity)
        elif _SHARED_CAPACITY != capacity:
            raise LlmClientConfigurationError("Conflicting process-wide LLM concurrency capacity.")
        return _SHARED_LIMITER


def _api_key_from_env() -> str | None:
    return os.getenv("OPENAI_API_KEY", "").strip() or os.getenv("LLM_API_KEY", "").strip() or None


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
    timeout_seconds: float = 20.0
    max_retries: int = 1
    max_output_tokens: int = 400
    max_concurrency: int = 5
    embedding_api_url: str = EMBEDDING_API_URL
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int | None = None
    embedding_timeout_seconds: float = 20.0
    embedding_max_retries: int = 1
    embedding_max_batch_size: int = 64
    embedding_max_text_chars: int = 8000

    def __post_init__(self) -> None:
        if not self.api_url.strip() or not self.embedding_api_url.strip():
            raise LlmClientConfigurationError("LLM and embedding endpoints must be non-empty.")
        if not self.model.strip() or not self.embedding_model.strip():
            raise LlmClientConfigurationError("LLM and embedding models must be non-empty.")
        positive = (
            ("timeout_seconds", self.timeout_seconds),
            ("embedding_timeout_seconds", self.embedding_timeout_seconds),
            ("max_output_tokens", self.max_output_tokens),
            ("max_concurrency", self.max_concurrency),
            ("embedding_max_batch_size", self.embedding_max_batch_size),
            ("embedding_max_text_chars", self.embedding_max_text_chars),
        )
        if any(value <= 0 for _, value in positive):
            raise LlmClientConfigurationError("LLM numeric settings must be positive.")
        if self.max_retries < 0 or self.embedding_max_retries < 0:
            raise LlmClientConfigurationError("LLM retry settings must be non-negative.")
        if self.embedding_dimensions is not None and self.embedding_dimensions <= 0:
            raise LlmClientConfigurationError("Embedding dimensions must be positive.")

    @classmethod
    def from_env(cls) -> "LlmSettings":
        explicit_url = os.getenv("LLM_API_URL", "").strip()
        api_url = explicit_url or os.getenv("LLM_BASE_URL", "").strip() or "https://api.openai.com/v1/chat/completions"
        if not explicit_url:
            api_url = api_url.rstrip("/")
            if api_url.endswith("/v1"):
                api_url += "/chat/completions"
            elif not api_url.endswith("/chat/completions"):
                api_url += "/v1/chat/completions"

        return cls(
            api_url=api_url,
            api_key=_api_key_from_env(),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "20")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "1")),
            max_output_tokens=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "400")),
            max_concurrency=int(os.getenv("MAX_LLM_CONCURRENCY", "5")),
            embedding_api_url=os.getenv("EMBEDDING_API_URL", "").strip() or EMBEDDING_API_URL,
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip() or "text-embedding-3-small",
            embedding_dimensions=(int(os.environ["EMBEDDING_DIMENSIONS"]) if os.getenv("EMBEDDING_DIMENSIONS", "").strip() else None),
            embedding_timeout_seconds=float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "20")),
            embedding_max_retries=int(os.getenv("EMBEDDING_MAX_RETRIES", "1")),
            embedding_max_batch_size=int(os.getenv("EMBEDDING_MAX_BATCH_SIZE", "64")),
            embedding_max_text_chars=int(os.getenv("EMBEDDING_MAX_TEXT_CHARS", "8000")),
        )


class LlmClient:
    """Minimal OpenAI-compatible client used by intelligence builders."""

    def __init__(
        self,
        settings: LlmSettings | None = None,
        http_client: httpx.AsyncClient | None = None,
        limiter: SharedAsyncLimiter | None = None,
    ) -> None:
        self.settings = settings or LlmSettings.from_env()
        self._client = http_client
        if limiter is not None and limiter.capacity != self.settings.max_concurrency:
            raise LlmClientConfigurationError("Injected limiter capacity conflicts with client settings.")
        self._concurrency_limiter = limiter or shared_limiter(self.settings.max_concurrency)

    def new_loop_local_embedding_client(self) -> "LlmClient":
        """Create loop-local HTTP client while retaining settings and process limiter."""
        return LlmClient(settings=self.settings, limiter=self._concurrency_limiter)

    async def call(
        self,
        messages: list[dict[str, Any]],
        response_model: type[T],
    ) -> T:
        async with self._concurrency_limiter:
            return await self._call_unlimited(messages, response_model)

    async def _call_unlimited(
        self,
        messages: list[dict[str, Any]],
        response_model: type[T],
    ) -> T:
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": self.settings.max_output_tokens,
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

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed one bounded batch without deriving endpoint from chat settings."""
        if not isinstance(texts, list):
            raise LlmClientConfigurationError("Embedding input must be a list of texts.")
        if not texts:
            return []
        if len(texts) > self.settings.embedding_max_batch_size:
            raise LlmClientConfigurationError("Embedding batch exceeds configured bounds.")
        for text in texts:
            if not isinstance(text, str) or not text.strip() or len(text) > self.settings.embedding_max_text_chars:
                raise LlmClientConfigurationError("Embedding text exceeds configured bounds.")
        async with self._concurrency_limiter:
            return await self._embed_batch(texts)

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, Any] = {"model": self.settings.embedding_model, "input": texts}
        if self.settings.embedding_dimensions is not None:
            payload["dimensions"] = self.settings.embedding_dimensions
        headers = {"Content-Type": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        last_timeout: httpx.TimeoutException | None = None
        for _ in range(max(self.settings.embedding_max_retries, 0) + 1):
            try:
                response = await self._post(payload=payload, headers=headers, timeout_seconds=self.settings.embedding_timeout_seconds, api_url=self.settings.embedding_api_url)
                response.raise_for_status()
                return self._parse_embeddings(response.json(), len(texts))
            except httpx.TimeoutException as exc:
                last_timeout = exc
                continue
            except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise LlmClientError(f"Embedding request failed: {exc}") from exc
        raise LlmClientTimeoutError("Embedding request timed out after retries.") from last_timeout

    def _parse_embeddings(self, payload: Any, expected_count: int) -> list[list[float]]:
        if not isinstance(payload, dict):
            raise LlmClientError("Embedding response must be an object.")
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != expected_count:
            raise LlmClientError("Embedding response count mismatch.")
        vectors: list[list[float] | None] = [None] * expected_count
        for item in data:
            if not isinstance(item, dict) or isinstance(item.get("index"), bool) or not isinstance(item.get("index"), int):
                raise LlmClientError("Embedding response index is invalid.")
            index = item["index"]
            if index < 0 or index >= expected_count or vectors[index] is not None:
                raise LlmClientError("Embedding response indexes are invalid.")
            raw_vector = item.get("embedding")
            if not isinstance(raw_vector, list) or not raw_vector or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in raw_vector):
                raise LlmClientError("Embedding vector contains invalid values.")
            vector = [float(value) for value in raw_vector]
            if self.settings.embedding_dimensions is not None and len(vector) != self.settings.embedding_dimensions:
                raise LlmClientError("Embedding dimension mismatch.")
            vectors[index] = vector
        if any(vector is None for vector in vectors):
            raise LlmClientError("Embedding response indexes are incomplete.")
        dimensions = {len(vector) for vector in vectors if vector is not None}
        if len(dimensions) != 1:
            raise LlmClientError("Embedding vectors have inconsistent dimensions.")
        return [vector for vector in vectors if vector is not None]

    async def _post(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: float | None = None,
        api_url: str | None = None,
    ) -> httpx.Response:
        if self._client is not None:
            return await self._client.post(
                api_url or self.settings.api_url,
                json=payload,
                headers=headers,
                timeout=timeout_seconds if timeout_seconds is not None else self.settings.timeout_seconds,
            )

        async with httpx.AsyncClient(timeout=timeout_seconds if timeout_seconds is not None else self.settings.timeout_seconds) as client:
            return await client.post(
                api_url or self.settings.api_url,
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
