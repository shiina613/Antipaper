from __future__ import annotations

import asyncio
import re

import pytest

from src.intelligence import DocumentChunk, NormalizedDocument
from src.intelligence.llm_pipeline import (
    CriticalQuestions,
    EvidenceFinding,
    GeneratedQuestion,
    IntelligenceQualityError,
    LlmIntelligencePipeline,
    LlmPipelineSettings,
    MapBatch,
    ReducedSummary,
    StrictIntelligenceSummary,
)
from src.intelligence.contracts import EvidenceItem


class FakeLlm:
    def __init__(self, *, invalid_map_citation: bool = False) -> None:
        self.invalid_map_citation = invalid_map_citation
        self.map_inputs: list[str] = []

    async def call(self, messages, response_model):  # noqa: ANN001
        if response_model is MapBatch:
            source = messages[-1]["content"]
            self.map_inputs.append(source)
            ids = re.findall(r"P\d+-D\d+", source)
            citation_ids = ["UNKNOWN"] if self.invalid_map_citation else list(dict.fromkeys(ids))
            return MapBatch(findings=[EvidenceFinding(kind="main_content", text="Nội dung đã được tổng hợp.", citation_ids=citation_ids)])
        if response_model is ReducedSummary:
            citation_ids = ["P1-D1"]
            return ReducedSummary(
                summary=StrictIntelligenceSummary(
                    context=[EvidenceItem(text="Tài liệu xác định phạm vi và chủ thể áp dụng.", citation_ids=citation_ids)],
                    main_content=[EvidenceItem(text="Tài liệu đặt ra các nghĩa vụ và phương án thực hiện.", citation_ids=citation_ids)],
                    decision_points=[EvidenceItem(text="Cần chốt chủ thể chịu trách nhiệm và phương án triển khai.", citation_ids=citation_ids)],
                    impact=[EvidenceItem(text="Việc thực hiện tạo nghĩa vụ tuân thủ và rủi ro chậm tiến độ.", citation_ids=citation_ids)],
                )
            )
        if response_model is CriticalQuestions:
            return CriticalQuestions(
                suggested_questions=[
                    GeneratedQuestion(
                        question=f"Đơn vị sẽ kiểm soát điều kiện triển khai số {index} như thế nào?",
                        rationale="Câu hỏi kiểm tra trách nhiệm và điều kiện thực hiện nêu trong tài liệu.",
                        citation_ids=["P1-D1"],
                    )
                    for index in range(1, 6)
                ]
            )
        raise AssertionError(f"Unexpected model: {response_model}")


def document() -> NormalizedDocument:
    chunks = [
        DocumentChunk(chunk_id=f"P{index}-D1", page=index, text=f"Nội dung nguồn số {index} có nghĩa vụ riêng.")
        for index in range(1, 5)
    ]
    return NormalizedDocument(document_id="test", file_name="test.pdf", page_count=4, chunks=chunks)


def test_map_reduce_covers_all_chunks_and_returns_grounded_summary_and_questions() -> None:
    llm = FakeLlm()
    pipeline = LlmIntelligencePipeline(llm, LlmPipelineSettings(map_batch_chars=50, map_concurrency=3))

    result = asyncio.run(pipeline.generate(document()))

    submitted = "\n".join(llm.map_inputs)
    assert all(chunk.chunk_id in submitted for chunk in document().chunks)
    assert result.map_batch_count == 4
    assert all(getattr(result.summary, section) for section in ("context", "main_content", "decision_points", "impact"))
    assert len(result.suggested_questions) == 5
    assert len({question.question for question in result.suggested_questions}) == 5
    assert all(question.citation_ids for question in result.suggested_questions)


def test_invalid_map_citation_fails_closed() -> None:
    pipeline = LlmIntelligencePipeline(FakeLlm(invalid_map_citation=True), LlmPipelineSettings(map_batch_chars=100))

    with pytest.raises(IntelligenceQualityError, match="valid citation"):
        asyncio.run(pipeline.generate(document()))
