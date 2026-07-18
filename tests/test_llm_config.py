from __future__ import annotations

from backend.llm import build_shared_llm_client


def test_blank_base_url_uses_openai_default(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_BASE_URL", "   ")

    client = build_shared_llm_client()

    assert client is not None
    assert client.base_url == "https://api.openai.com/v1"
