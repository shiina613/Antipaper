from __future__ import annotations

import asyncio
import json
from pathlib import Path

from backend.service import AntipaperService, DocumentRecord
from backend.orchestrator import ProcessedDocument
from intelligence import NormalizedDocument


ROOT = Path(__file__).parents[1]


def normalized() -> NormalizedDocument:
    return NormalizedDocument.model_validate(json.loads((ROOT / "docs/fixtures/normalized_document.mock.json").read_text(encoding="utf-8")))


class FakeLlmClient:
    def __init__(self, failure: bool = False):
        self.messages = []
        self.failure = failure

    async def call(self, messages, response_model):
        self.messages.append(messages)
        if self.failure:
            raise RuntimeError("fake transport failure")
        return response_model.model_validate({
            "answer": normalized().chunks[1].text,
            "citation_ids": ["P3-D2"],
        })


def service_with_document(client=None) -> AntipaperService:
    service = AntipaperService(llm_client=client)
    doc = normalized()
    service.store._documents["demo"] = DocumentRecord(
        document_id="demo",
        file_name=doc.file_name,
        file_size_bytes=0,
        file_bytes=b"",
        status="completed",
        processed_document=ProcessedDocument(doc.file_name, doc.page_count, [], normalized_document=doc),
    )
    return service


def test_antipaper_service_uses_injected_shared_llm_client():
    fake = FakeLlmClient()
    service = service_with_document(fake)
    try:
        response = asyncio.run(service.answer_question("demo", "Kinh phí lấy từ đâu?"))
        assert response.citation_ids == ["P3-D2"]
        assert fake.messages[0][0]["role"] == "system"
        assert fake.messages[0][1]["role"] == "user"
    finally:
        service.shutdown()


def test_no_key_and_client_error_keep_extractable_fallback(monkeypatch):
    for name in ("OPENAI_API_KEY", "LLM_API_KEY", "LLM_API_URL", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    for client in (None, FakeLlmClient(failure=True)):
        service = service_with_document(client)
        try:
            response = asyncio.run(service.answer_question("demo", "Kinh phí lấy từ đâu?"))
            assert response.citation_ids == ["P3-D2"]
            assert response.insufficient_evidence is False
            assert response.answer.startswith("Kinh phí")
        finally:
            service.shutdown()


def test_real_quyet_dinh_pdf_qa_uses_extractive_fallback(monkeypatch):
    for name in ("OPENAI_API_KEY", "LLM_API_KEY", "LLM_API_URL", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    pdf_path = ROOT / "data" / "quyet_dinh.pdf"
    if not pdf_path.exists():
        return
    service = AntipaperService()
    try:
        upload = service.submit_document(pdf_path.name, pdf_path.read_bytes())
        response = asyncio.run(service.answer_question(
            upload.document_id,
            "Quyết định số 04/2021/QĐ-UBND quy định gì về an toàn thực phẩm?",
        ))
        assert "04/2021/QĐ-UBND" in response.answer
        assert response.citation_ids
        assert response.insufficient_evidence is False
    finally:
        service.shutdown()


def test_real_quyet_dinh_pdf_rejects_cited_gpt_paraphrase(monkeypatch):
    for name in ("OPENAI_API_KEY", "LLM_API_KEY", "LLM_API_URL", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    class InventingDecisionClient:
        async def call(self, messages, response_model):
            return response_model.model_validate({
                "answer": "Quyết định số 04/2021/QĐ-UBND quy định xử phạt 999 triệu đồng.",
                "citation_ids": ["P1-D1"],
            })

    pdf_path = ROOT / "data" / "quyet_dinh.pdf"
    if not pdf_path.exists():
        return
    service = AntipaperService(llm_client=InventingDecisionClient())
    try:
        upload = service.submit_document(pdf_path.name, pdf_path.read_bytes())
        response = asyncio.run(service.answer_question(
            upload.document_id,
            "Quyết định số 04/2021/QĐ-UBND quy định gì về an toàn thực phẩm?",
        ))
        assert "04/2021/QĐ-UBND" in response.answer
        assert "999 triệu" not in response.answer
        assert response.citation_ids
    finally:
        service.shutdown()


def test_real_quyet_dinh_pdf_extracts_requested_decision_number(monkeypatch):
    for name in ("OPENAI_API_KEY", "LLM_API_KEY", "LLM_API_URL", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    pdf_path = ROOT / "data" / "quyet_dinh.pdf"
    if not pdf_path.exists():
        return
    service = AntipaperService()
    try:
        upload = service.submit_document(pdf_path.name, pdf_path.read_bytes())
        response = asyncio.run(service.answer_question(
            upload.document_id,
            "Số hiệu của Quyết định được sửa đổi, bổ sung là gì?",
        ))
        assert response.answer == "04/2021/QĐ-UBND"
        assert response.citation_ids
        assert response.insufficient_evidence is False
    finally:
        service.shutdown()
