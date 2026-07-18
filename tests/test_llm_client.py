from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from llm import LlmClient, LlmClientError, LlmClientTimeoutError, LlmSettings, shared_limiter


class DemoResponse(BaseModel):
    value: str


def test_llm_client_validates_openai_style_json_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"value": "ok"})}},
                ]
            },
        )

    client = LlmClient(
        settings=LlmSettings(api_url="https://llm.local/chat", max_retries=0),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = asyncio.run(client.call([{"role": "user", "content": "hi"}], DemoResponse))
    assert result == DemoResponse(value="ok")


def test_llm_client_rejects_invalid_schema() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"wrong": "field"})}}]},
        )

    client = LlmClient(
        settings=LlmSettings(api_url="https://llm.local/chat", max_retries=0),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(LlmClientError, match="schema validation"):
        asyncio.run(client.call([{"role": "user", "content": "hi"}], DemoResponse))


def test_llm_client_retries_timeouts() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.TimeoutException("timeout")

    client = LlmClient(
        settings=LlmSettings(
            api_url="https://llm.local/chat",
            timeout_seconds=0.01,
            max_retries=2,
        ),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(LlmClientTimeoutError):
        asyncio.run(client.call([{"role": "user", "content": "hi"}], DemoResponse))
    assert calls == 3


def test_env_url_precedence_and_authorization_header(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "  preferred-key  ")
    monkeypatch.setenv("LLM_API_KEY", "compat-key")
    monkeypatch.setenv("LLM_API_URL", "https://explicit.invalid/custom")
    monkeypatch.setenv("LLM_BASE_URL", "https://ignored.invalid/v1")
    settings = LlmSettings.from_env()
    assert settings.api_url == "https://explicit.invalid/custom"
    assert settings.api_key == "preferred-key"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer preferred-key"
        return httpx.Response(200, json={"value": "ok"})

    client = LlmClient(settings=settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert asyncio.run(client.call([], DemoResponse)).value == "ok"


def test_base_url_normalizes_to_chat_completions(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_URL", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example/v1/")
    assert LlmSettings.from_env().api_url == "https://api.example/v1/chat/completions"


def test_embedding_payload_auth_endpoint_and_response_order() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert str(request.url) == "https://embed.local/v1/embeddings"
        assert request.headers["authorization"] == "Bearer embedding-key"
        assert payload["model"] == "text-embedding-3-small"
        assert payload["input"] == ["one", "two"]
        assert payload["dimensions"] == 3
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [2, 2, 2]},
            {"index": 0, "embedding": [1, 1, 1]},
        ]})

    client = LlmClient(
        settings=LlmSettings(api_url="unused", api_key="embedding-key", embedding_api_url="https://embed.local/v1/embeddings", embedding_dimensions=3),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    assert asyncio.run(client.embed(["one", "two"])) == [[1.0, 1.0, 1.0], [2.0, 2.0, 2.0]]


def test_embedding_empty_input_and_bounds_do_not_network() -> None:
    class NoNetwork(LlmClient):
        async def _post(self, **kwargs):
            raise AssertionError("network called")

    client = NoNetwork(settings=LlmSettings(api_url="unused", embedding_max_batch_size=1, embedding_max_text_chars=3))
    assert asyncio.run(client.embed([])) == []
    for invalid in (None, (), "text"):
        with pytest.raises(LlmClientError):
            asyncio.run(client.embed(invalid))  # type: ignore[arg-type]
    with pytest.raises(LlmClientError):
        asyncio.run(client.embed(["one", "two"]))
    with pytest.raises(LlmClientError):
        asyncio.run(client.embed(["long"]))


def test_embedding_rejects_malformed_vectors_and_indexes():
    async def call_with(data):
        async def handler(request):
            return httpx.Response(200, json={"data": data})
        client = LlmClient(settings=LlmSettings(api_url="unused"), http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        with pytest.raises(LlmClientError):
            await client.embed(["a", "b"])

    asyncio.run(call_with([{"index": 0, "embedding": [1, 2]}, {"index": 0, "embedding": [3, 4]}]))
    asyncio.run(call_with([{"index": 0, "embedding": [1, 2]}, {"index": 2, "embedding": [3, 4]}]))
    asyncio.run(call_with([{"index": 0, "embedding": [1, float("nan")]}, {"index": 1, "embedding": [3, 4]}]))
    asyncio.run(call_with([{"index": 0, "embedding": [1, 2]}, {"index": 1, "embedding": [3]}]))

    async def bool_index(request):
        return httpx.Response(200, json={"data": [{"index": True, "embedding": [1]}, {"index": 1, "embedding": [2]}]}, request=request)
    client = LlmClient(settings=LlmSettings(api_url="unused"), http_client=httpx.AsyncClient(transport=httpx.MockTransport(bool_index)))
    with pytest.raises(LlmClientError):
        asyncio.run(client.embed(["a", "b"]))


def test_embedding_rejects_non_object_payload_and_configured_dimension_mismatch():
    async def non_object(request):
        return httpx.Response(200, json=[{"index": 0, "embedding": [1]}], request=request)

    client = LlmClient(settings=LlmSettings(api_url="unused"), http_client=httpx.AsyncClient(transport=httpx.MockTransport(non_object)))
    with pytest.raises(LlmClientError):
        asyncio.run(client.embed(["a"]))

    async def wrong_dimension(request):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1]}]}, request=request)

    client = LlmClient(settings=LlmSettings(api_url="unused", embedding_dimensions=2), http_client=httpx.AsyncClient(transport=httpx.MockTransport(wrong_dimension)))
    with pytest.raises(LlmClientError):
        asyncio.run(client.embed(["a"]))


def test_invalid_embedding_settings_fail_eagerly():
    invalid: tuple[dict[str, Any], ...] = (
        {"api_url": ""},
        {"api_url": "x", "embedding_model": ""},
        {"api_url": "x", "embedding_timeout_seconds": 0},
        {"api_url": "x", "embedding_max_batch_size": 0},
        {"api_url": "x", "embedding_max_text_chars": 0},
        {"api_url": "x", "embedding_dimensions": 0},
        {"api_url": "x", "embedding_max_retries": -1},
        {"api_url": "x", "max_concurrency": 0},
    )
    for values in invalid:
        with pytest.raises(LlmClientError):
            LlmSettings(**values)


def test_embedding_retries_timeout():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.TimeoutException("timeout")
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]}, request=request)

    client = LlmClient(settings=LlmSettings(api_url="unused", embedding_max_retries=1), http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert asyncio.run(client.embed(["a"])) == [[1.0]]
    assert calls == 2


def test_embedding_limiter_caps_calls_across_event_loops():
    active = 0
    maximum = 0
    lock = threading.Lock()
    errors: list[BaseException] = []

    class ProbeClient(LlmClient):
        async def _post(self, **kwargs):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            await asyncio.sleep(0.02)
            with lock:
                active -= 1
            payload = kwargs["payload"]
            if "messages" in payload:
                body = {"choices": [{"message": {"content": json.dumps({"value": "ok"})}}]}
            else:
                body = {"data": [{"index": 0, "embedding": [1.0]}]}
            return httpx.Response(200, json=body, request=httpx.Request("POST", "https://embed.local"))

    limiter = shared_limiter(5)

    def run_many():
        client = ProbeClient(settings=LlmSettings(api_url="unused", max_concurrency=5), limiter=limiter)
        async def run():
            await asyncio.gather(client.embed(["x"]), client.call([], DemoResponse))
        try:
            asyncio.run(run())
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run_many) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert maximum <= 5
    assert errors == []


def test_shared_client_limits_concurrent_calls() -> None:
    active = 0
    maximum = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, json={"value": "ok"})

    client = LlmClient(
        settings=LlmSettings(api_url="https://llm.local/chat", max_concurrency=5),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    async def run():
        await asyncio.gather(*(client.call([], DemoResponse) for _ in range(7)))

    asyncio.run(run())
    assert maximum <= 5
