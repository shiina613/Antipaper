from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel

from llm import LlmClient, LlmClientError, LlmClientTimeoutError, LlmSettings


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
