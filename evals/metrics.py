"""DeepEval metric factories and deterministic release gates."""

from __future__ import annotations

from typing import Any

from deepeval.metrics import (
    AnswerRelevancyMetric,
    BaseMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, SingleTurnParams


class CitationPrecisionMetric(BaseMetric):
    def __init__(
        self,
        *,
        actual_ids: list[str],
        accepted_ids: list[str],
        threshold: float = 0.90,
    ) -> None:
        self.threshold = threshold
        self.actual_ids = actual_ids
        self.accepted_ids = set(accepted_ids)
        self.evaluation_model = "deterministic"
        self.include_reason = True
        self.async_mode = False
        self.strict_mode = False
        self.score: float | None = None
        self.reason: str | None = None
        self.success: bool | None = None

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        del test_case, args, kwargs
        if not self.actual_ids:
            self.score = 0.0
        else:
            self.score = sum(item in self.accepted_ids for item in self.actual_ids) / len(
                self.actual_ids
            )
        self.reason = f"{self.score:.2%} citation IDs belong to the accepted evidence set."
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)


class RefusalMetric(BaseMetric):
    def __init__(
        self,
        *,
        insufficient_evidence: bool,
        citation_ids: list[str],
    ) -> None:
        self.threshold = 1.0
        self.insufficient_evidence = insufficient_evidence
        self.citation_ids = citation_ids
        self.evaluation_model = "deterministic"
        self.include_reason = True
        self.async_mode = False
        self.strict_mode = True
        self.score: float | None = None
        self.reason: str | None = None
        self.success: bool | None = None

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        del test_case, args, kwargs
        self.score = float(self.insufficient_evidence and not self.citation_ids)
        self.reason = "Refusal requires insufficient_evidence=true and zero citations."
        self.success = self.score == 1.0
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)


def answerable_qa_metrics(
    *,
    judge_model: Any,
    actual_citation_ids: list[str],
    accepted_citation_ids: list[str],
) -> list[BaseMetric]:
    return [
        ContextualPrecisionMetric(threshold=0.80, model=judge_model),
        ContextualRecallMetric(threshold=0.80, model=judge_model),
        ContextualRelevancyMetric(threshold=0.80, model=judge_model),
        FaithfulnessMetric(threshold=0.90, model=judge_model),
        AnswerRelevancyMetric(threshold=0.80, model=judge_model),
        GEval(
            name="Vietnamese grounded answer correctness",
            evaluation_steps=[
                "Đối chiếu từng khẳng định trong actual output với expected output.",
                "Phạt nặng thông tin mâu thuẫn hoặc bổ sung sự kiện không có trong expected output.",
                "Chấp nhận cách diễn đạt khác nếu giữ đúng ý nghĩa pháp lý cốt lõi.",
                "Đánh giá mức đầy đủ đối với chính câu hỏi, không yêu cầu chép nguyên văn.",
            ],
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            threshold=0.80,
            model=judge_model,
        ),
        CitationPrecisionMetric(
            actual_ids=actual_citation_ids,
            accepted_ids=accepted_citation_ids,
        ),
    ]


def meeting_quality_metric(*, name: str, judge_model: Any, threshold: float) -> GEval:
    return GEval(
        name=name,
        evaluation_steps=[
            "Kiểm tra actual output có cụ thể với tài liệu và không phải câu chữ chung chung.",
            "Đối chiếu tính đúng ngữ cảnh và ý nghĩa với expected output.",
            "Kiểm tra nội dung có hữu ích cho việc chuẩn bị hoặc ra quyết định trong cuộc họp.",
            "Chỉ cho điểm đạt khi nội dung rõ ràng, không mâu thuẫn và có đủ ý cốt lõi.",
        ],
        evaluation_params=[
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        threshold=threshold,
        model=judge_model,
    )
