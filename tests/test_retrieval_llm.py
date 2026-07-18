from __future__ import annotations

import asyncio
import json
from pathlib import Path

from intelligence import NormalizedDocument
from llm import LlmSettings
from retrieval import GroundedQAService, GroundedLlmResponse, LlmRagAdapter, build_index


ROOT = Path(__file__).parents[1]


def document() -> NormalizedDocument:
    payload = json.loads((ROOT / "docs/fixtures/normalized_document.mock.json").read_text(encoding="utf-8"))
    return NormalizedDocument.model_validate(payload)


class FakeLlmClient:
    def __init__(self, response):
        self.response = response
        self.messages = []

    async def call(self, messages, response_model):
        self.messages.append(messages)
        return response_model.model_validate(self.response)


def test_adapter_uses_shared_client_and_structured_gpt_default():
    client = FakeLlmClient({"answer": "Kinh phí thực hiện lấy từ ngân sách được giao.", "citation_ids": ["P3-D2"]})
    result = asyncio.run(LlmRagAdapter(client)({"question": "q", "context": "[P3-D2] source"}))
    assert isinstance(result, GroundedLlmResponse)
    assert client.messages[0][0]["role"] == "system"
    assert "BEGIN_UNTRUSTED_RETRIEVED_CONTEXT" in client.messages[0][1]["content"]
    assert LlmSettings(api_url="https://api.openai.com/v1/chat/completions").model == "gpt-4o-mini"


def test_openai_key_precedes_compatibility_key_and_url_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "preferred")
    monkeypatch.setenv("LLM_API_KEY", "compat")
    monkeypatch.delenv("LLM_API_URL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    settings = LlmSettings.from_env()
    assert settings.api_key == "preferred"
    assert settings.model == "gpt-4o-mini"
    assert settings.api_url == "https://api.openai.com/v1/chat/completions"


def test_backend_style_grounded_qa_accepts_supported_paraphrase():
    client = FakeLlmClient({"answer": "Kinh phí lấy từ ngân sách được giao.", "citation_ids": ["P3-D2"]})
    result = asyncio.run(GroundedQAService(build_index(document()), LlmRagAdapter(client)).answer("kinh phí ngân sách"))
    assert result.citation_ids == ["P3-D2"]
    assert not result.insufficient_evidence


def test_invalid_citation_and_client_failure_fall_back_safely():
    invalid = FakeLlmClient({"answer": "Ngân sách là một triệu đồng.", "citation_ids": ["P99"]})
    result = asyncio.run(GroundedQAService(build_index(document()), LlmRagAdapter(invalid)).answer("kinh phí ngân sách"))
    assert result.citation_ids == ["P3-D2"]
    assert result.answer.startswith("Kinh phí")

    class BrokenClient:
        async def call(self, messages, response_model):
            raise RuntimeError("transport failure")

    fallback = asyncio.run(GroundedQAService(build_index(document()), LlmRagAdapter(BrokenClient())).answer("kinh phí ngân sách"))
    assert fallback.citation_ids == ["P3-D2"]
    assert fallback.answer.startswith("Kinh phí")
