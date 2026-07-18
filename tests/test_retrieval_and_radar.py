from __future__ import annotations

import asyncio

from decision import DecisionRadarEngine
from intelligence import Citation, DocumentChunk, NormalizedDocument
from retrieval import GroundedQAService, build_index
from summary import DocumentSummaryEngine


def make_document() -> NormalizedDocument:
    chunks = [
        DocumentChunk(
            chunk_id="P1-D1",
            page=1,
            text="Điều 1. Ủy ban nhân dân tỉnh quyết định phê duyệt kế hoạch chuyển đổi số.",
            article="Điều 1",
        ),
        DocumentChunk(
            chunk_id="P2-D1",
            page=2,
            text="Sở Tài chính chịu trách nhiệm bố trí kinh phí và báo cáo trước tháng 12.",
            article="Điều 2",
            clause="Khoản 1",
        ),
    ]
    return NormalizedDocument(
        document_id="demo",
        file_name="demo.pdf",
        page_count=2,
        chunks=chunks,
        citations={
            chunk.chunk_id: Citation(
                page=chunk.page,
                article=chunk.article,
                clause=chunk.clause,
                excerpt=chunk.text,
            )
            for chunk in chunks
        },
    )


def test_grounded_qa_answers_with_chunk_citations() -> None:
    answer = asyncio.run(
        GroundedQAService(build_index(make_document())).answer(
            "Ai chịu trách nhiệm bố trí kinh phí?"
        )
    )

    assert answer.insufficient_evidence is False
    assert answer.citation_ids == ["P2-D1"]
    assert "Sở Tài chính" in answer.answer


def test_grounded_qa_refuses_out_of_scope_question() -> None:
    answer = asyncio.run(
        GroundedQAService(build_index(make_document())).answer(
            "Giá xăng hôm nay là bao nhiêu?"
        )
    )

    assert answer.insufficient_evidence is True
    assert answer.citation_ids == []


def test_decision_radar_extracts_key_categories() -> None:
    radar = DecisionRadarEngine().build(make_document())

    assert radar.decision_points
    assert radar.responsibilities
    assert radar.resources
    assert radar.deadlines


def test_decision_radar_llm_filters_invalid_citations() -> None:
    class FakeLlm:
        async def call(self, messages, response_model):  # noqa: ANN001
            assert messages
            return response_model(
                decision_points=[
                    {
                        "category": "Vấn đề cần quyết định",
                        "finding": "Cần phê duyệt kế hoạch chuyển đổi số.",
                        "confidence": "high",
                        "citation_ids": ["P1-D1", "P99"],
                    }
                ],
                risks=[
                    {
                        "category": "Rủi ro",
                        "finding": "Không có nguồn hợp lệ.",
                        "confidence": 0.7,
                        "citation_ids": ["P99"],
                    }
                ],
            )

    radar = asyncio.run(
        DecisionRadarEngine().build_with_llm(make_document(), llm_client=FakeLlm())
    )

    assert radar.decision_points[0].citation_ids == ["P1-D1"]
    assert radar.risks == []


def test_document_summary_uses_chunk_citations() -> None:
    summary = DocumentSummaryEngine().build(make_document())

    assert summary.executive_summary or summary.context or summary.main_content
    all_items = [
        *summary.executive_summary,
        *summary.context,
        *summary.main_content,
        *summary.decision_points,
        *summary.impact,
        *summary.risks,
    ]
    assert all(item.citation_ids for item in all_items)
