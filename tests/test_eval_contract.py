from __future__ import annotations

import asyncio
import json
from pathlib import Path

from backend.orchestrator import DocumentOrchestrator
from backend.service import AntipaperService
from evals.adapters import BenchmarkApplication
from evals.dataset import load_release_records
from backend.intelligence import IntelligenceDraft
from backend.retrieval import load_golden_cases


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "datasets" / "demo_v1.jsonl"


def test_release_dataset_has_required_coverage_and_valid_citations() -> None:
    records = load_release_records(DATASET)
    assert len([item for item in records if item.record_type == "qa" and item.scope == "in"]) == 10
    assert len([item for item in records if item.record_type == "qa" and item.scope == "out"]) == 3
    assert {item.section for item in records if item.record_type == "summary"} == {
        "context",
        "main_content",
        "decision_points",
        "impact",
    }
    assert len([item for item in records if item.record_type == "term"]) >= 10
    assert len([item for item in records if item.record_type == "suggested_question"]) >= 5

    app = BenchmarkApplication.from_path(
        ROOT / records[0].document_path,
        use_configured_llm=False,
    )
    accepted_ids = app.document.citation_whitelist
    assert app.document.page_count == 44
    assert all(set(item.gold_citation_ids).issubset(accepted_ids) for item in records)


def test_existing_golden_loader_reuses_release_jsonl() -> None:
    cases = load_golden_cases(DATASET)
    assert len(cases) == 13
    assert sum(case.expected_out_of_scope for case in cases) == 3
    assert cases[0].expected_output


def test_backend_persists_normalized_document_and_uses_retrieval(
    tmp_path,
    monkeypatch,
) -> None:
    # This case explicitly verifies the offline fallback path and must not
    # inherit a developer's configured model credentials from .env.
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    source = ROOT / "data" / "bien_ban_hop.pdf"
    service = AntipaperService(artifact_root=tmp_path)
    upload = service.submit_document(source.name, source.read_bytes())
    report = service.get_report(upload.document_id)
    assert report.generation_mode == "heuristic_fallback"

    response = asyncio.run(
        service.answer_question(
            upload.document_id,
            "Mục đích xem xét hệ thống quản lý chất lượng là gì?",
        )
    )
    record = service.store.get(upload.document_id)
    assert record.normalized_document is not None
    assert record.retrieval_index is not None
    assert record.last_question_trace is not None
    assert response.citation_ids == list(record.last_question_trace.response.citation_ids)
    assert (tmp_path / "documents" / upload.document_id / "normalized.json").exists()


def test_configured_report_path_uses_intelligence_builder() -> None:
    source = ROOT / "data" / "bien_ban_hop.pdf"

    async def fake_call_llm(messages, response_model):  # noqa: ANN001
        assert response_model is IntelligenceDraft
        prompt = messages[-1]["content"]
        citation_id = "P1-D1"
        payload = {
            "summary": {
                "context": [{"text": "Bối cảnh cuộc họp ISO.", "citation_ids": [citation_id]}],
                "main_content": [{"text": "Đánh giá hệ thống quản lý.", "citation_ids": [citation_id]}],
                "decision_points": [{"text": "Cần thống nhất cải tiến.", "citation_ids": [citation_id]}],
                "impact": [{"text": "Nâng cao hiệu lực quản lý.", "citation_ids": [citation_id]}],
            },
            "terms": [
                {
                    "term": f"thuật ngữ {index}",
                    "explanation": "Giải thích theo tài liệu.",
                    "citation_ids": [citation_id],
                }
                for index in range(10)
            ],
            "suggested_questions": [
                {
                    "question": f"Trách nhiệm và rủi ro số {index} cần quyết định như thế nào?",
                    "rationale": "Làm rõ trách nhiệm và rủi ro.",
                    "citation_ids": [citation_id],
                }
                for index in range(5)
            ],
        }
        return payload

    result = DocumentOrchestrator(call_llm=fake_call_llm).process(
        document_id="configured-llm-test",
        file_name=source.name,
        file_bytes=source.read_bytes(),
    )
    assert result.report.generation_mode == "llm"
    assert result.report.quality is not None
    assert result.report.citations
