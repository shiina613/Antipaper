from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.intelligence import (
    EvidenceItem,
    IntelligenceBuilder,
    IntelligenceConfigurationError,
    IntelligenceDraft,
    IntelligenceReport,
    IntelligenceSummary,
    MeetingIntelligenceEngine,
    NormalizedDocument,
    build_intelligence,
)


ROOT = Path(__file__).resolve().parents[1]


def load_json(name: str) -> dict:
    return json.loads((ROOT / "docs" / "fixtures" / name).read_text(encoding="utf-8"))


def test_handoff_fixtures_match_contract_and_schema() -> None:
    document = NormalizedDocument.model_validate(load_json("normalized_document.mock.json"))
    report = IntelligenceReport.model_validate(load_json("intelligence_report.mock.json"))

    assert document.citation_whitelist == {"P1-D1", "P3-D2", "P5-D3", "P8-D4"}
    assert report.quality.passed is True
    assert "summary" in IntelligenceReport.model_json_schema()["properties"]


def test_document_rejects_duplicate_chunk_ids() -> None:
    payload = load_json("normalized_document.mock.json")
    payload["chunks"].append(payload["chunks"][0].copy())
    with pytest.raises(ValueError, match="unique"):
        NormalizedDocument.model_validate(payload)


def test_map_reduce_filters_unknown_citations_fail_closed() -> None:
    document = NormalizedDocument.model_validate(load_json("normalized_document.mock.json"))
    report_payload = load_json("intelligence_report.mock.json")
    draft_payload = {
        "summary": report_payload["summary"],
        "terms": report_payload["terms"],
        "suggested_questions": report_payload["suggested_questions"],
    }
    draft_payload["summary"]["context"].append(
        {"text": "Nội dung không có trong tài liệu.", "citation_ids": ["P99-FAKE"]}
    )
    calls: list[list[dict[str, str]]] = []

    async def fake_call_llm(messages, response_model):
        calls.append(messages)
        assert response_model is IntelligenceDraft
        return draft_payload

    report = asyncio.run(build_intelligence(document, call_llm=fake_call_llm))

    # Pages 1-7 and page 8 produce two map calls, followed by reduce, dedicated
    # term generation, and question generation over the final summary.
    assert len(calls) == 5
    term_prompt = calls[-2][-1]["content"]
    question_prompt = calls[-1][-1]["content"]
    assert "BATCH TERM CANDIDATES" in term_prompt
    assert "ít nhất 10 và không quá 100" in term_prompt
    assert "FINAL SUMMARY" in question_prompt
    assert "liệt kê đầy đủ" in question_prompt
    assert report_payload["summary"]["main_content"][0]["text"] in question_prompt
    all_ids = {
        citation_id
        for item in report.summary.context
        for citation_id in item.citation_ids
    }
    assert "P99-FAKE" not in all_ids
    assert report.quality.citations_valid is False
    assert report.quality.passed is False
    assert [timing.stage for timing in report.stage_timings] == [
        "map",
        "reduce",
        "term_generation",
        "question_generation",
        "validation",
    ]
    assert "không vượt quá 800 từ" in calls[-3][-1]["content"]
    assert "Mỗi EvidenceItem là một gạch đầu dòng" in calls[-3][-1]["content"]
    assert "đối chiếu lần lượt tất cả batch" in calls[-3][-1]["content"]


def test_summary_sections_keep_separate_bullets_and_grounded_sources() -> None:
    document = NormalizedDocument.model_validate(load_json("normalized_document.mock.json"))
    report_payload = load_json("intelligence_report.mock.json")
    draft_payload = {
        "summary": report_payload["summary"],
        "terms": report_payload["terms"],
        "suggested_questions": report_payload["suggested_questions"],
    }
    draft_payload["summary"]["context"] = [
        {"text": "Tài liệu xác định mục tiêu phục vụ người dân.", "citation_ids": ["P1-D1"]},
        {"text": "Phạm vi triển khai gắn với lộ trình và ngân sách.", "citation_ids": ["P3-D2", "P5-D3"]},
    ]

    async def fake_call_llm(messages, response_model):
        return draft_payload

    report = asyncio.run(build_intelligence(document, call_llm=fake_call_llm))

    assert len(report.summary.context) == 2
    assert report.summary.context[0].text == "Tài liệu xác định mục tiêu phục vụ người dân."
    assert report.summary.context[0].citation_ids == ["P1-D1"]
    assert report.summary.context[1].text == (
        "Phạm vi triển khai gắn với lộ trình và ngân sách."
    )
    assert report.summary.context[1].citation_ids == ["P3-D2", "P5-D3"]
    assert len(report.terms) <= 20
    assert all(len(term.citation_ids) == 1 for term in report.terms)


def test_summary_is_capped_at_800_words_without_dropping_a_section() -> None:
    def items(prefix: str, count: int) -> list[EvidenceItem]:
        return [
            EvidenceItem(
                text=" ".join(f"{prefix}{index}-{word}" for word in range(90)),
                citation_ids=["P1-D1"],
            )
            for index in range(count)
        ]

    summary = IntelligenceSummary(
        context=items("context", 4),
        main_content=items("main", 6),
        decision_points=items("decision", 4),
        impact=items("impact", 4),
    )

    limited = IntelligenceBuilder._limit_summary_words(summary)  # noqa: SLF001
    sections = (
        limited.context,
        limited.main_content,
        limited.decision_points,
        limited.impact,
    )
    total_words = sum(len(item.text.split()) for section in sections for item in section)

    assert total_words <= 800
    assert all(section for section in sections)


def test_empty_document_returns_empty_report_without_model_call() -> None:
    payload = load_json("normalized_document.mock.json")
    payload["chunks"] = []
    payload["citations"] = {}
    document = NormalizedDocument.model_validate(payload)
    calls = 0

    async def fake_call_llm(messages, response_model):
        nonlocal calls
        calls += 1
        return {}

    report = asyncio.run(build_intelligence(document, call_llm=fake_call_llm))
    assert calls == 0
    assert report.summary.context == []
    assert report.quality.passed is False


def test_heuristic_summary_prioritizes_actionable_decision_points() -> None:
    document = SimpleNamespace(
        stitched_pages=[
            SimpleNamespace(
                page_number=1,
                content=(
                    "Báo cáo trình bày kết quả doanh thu và tăng trưởng trong kỳ. "
                    "Nội dung chính bao gồm bối cảnh thị trường và số liệu vận hành."
                ),
            ),
            SimpleNamespace(
                page_number=2,
                content=(
                    "Chủ trì cần quyết định phương án triển khai, nguồn kinh phí "
                    "và giao trách nhiệm cho từng đơn vị trước ngày 30/09/2026."
                ),
            ),
        ],
    )

    report = MeetingIntelligenceEngine().build_report(document)

    assert report.summary.decision_points
    assert len(report.summary.decision_points) == 1
    assert "quyết định phương án triển khai" in report.summary.decision_points[0]
    assert "Trang 2" in report.summary.decision_points[0]


def test_heuristic_terms_are_capped_and_use_one_representative_page() -> None:
    engine = MeetingIntelligenceEngine()
    all_terms = list(engine._TERM_DICTIONARY)  # noqa: SLF001
    document = SimpleNamespace(
        stitched_pages=[
            SimpleNamespace(page_number=index + 1, content=". ".join(all_terms))
            for index in range(30)
        ],
    )

    report = engine.build_report(document)

    assert 10 <= len(report.terms) <= 100
    assert all(len(term.pages) == 1 for term in report.terms)


def test_heuristic_questions_include_document_specific_anchors() -> None:
    engine = MeetingIntelligenceEngine()
    first_document = SimpleNamespace(
        stitched_pages=[
            SimpleNamespace(
                page_number=1,
                content="Hội đồng xem xét đầu tư trung tâm dữ liệu tại khu vực phía Nam.",
            )
        ]
    )
    second_document = SimpleNamespace(
        stitched_pages=[
            SimpleNamespace(
                page_number=1,
                content="Nhà trường điều chỉnh tỷ trọng câu hỏi tự luận trong kỳ thi cuối khóa.",
            )
        ]
    )

    first_questions = engine.build_report(first_document).questions
    second_questions = engine.build_report(second_document).questions

    assert len(first_questions) == len(second_questions) == 5
    assert all("trung tâm dữ liệu" in item.question for item in first_questions)
    assert all("câu hỏi tự luận" in item.question for item in second_questions)
    assert {item.question for item in first_questions}.isdisjoint(
        item.question for item in second_questions
    )


def test_heuristic_questions_trace_all_supporting_pages_per_question() -> None:
    engine = MeetingIntelligenceEngine()
    shared_premise = (
        "Đề án chuyển đổi số quy định chỉ số đánh giá tiến độ và trách nhiệm "
        "giải trình của cơ quan chủ trì."
    )
    document = SimpleNamespace(
        stitched_pages=[
            SimpleNamespace(
                page_number=page,
                content=f"{shared_premise} Nội dung bằng chứng tại trang {page}.",
            )
            for page in range(1, 5)
        ],
    )

    questions = engine.build_report(document).questions

    assert len(questions) == 5
    assert all(
        set(item.citations) == {"Trang 1", "Trang 2", "Trang 3", "Trang 4"}
        for item in questions
    )


def test_shared_llm_client_is_required() -> None:
    document = NormalizedDocument.model_validate(load_json("normalized_document.mock.json"))
    with pytest.raises(IntelligenceConfigurationError):
        asyncio.run(build_intelligence(document))
