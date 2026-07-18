"""Deterministic local intelligence helpers.

Terminology is evidence-first: it never pads a list with generic dictionary words.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import NormalizedDocument, SuggestedQuestion, TermExplanation
from .terminology import build_terminology_result


@dataclass(frozen=True)
class LocalIntelligencePack:
    terms: list[TermExplanation]
    suggested_questions: list[SuggestedQuestion]


def build_local_intelligence_pack(
    document: NormalizedDocument,
    *,
    minimum_terms: int = 0,
    minimum_questions: int = 5,
) -> LocalIntelligencePack:
    """Compatibility wrapper for deterministic callers.

    ``minimum_terms`` is intentionally ignored: legal terminology is not a quota.
    """

    return LocalIntelligencePack(
        terms=detect_terms(document, minimum=minimum_terms),
        suggested_questions=suggest_questions(document, minimum=minimum_questions),
    )


def detect_terms(document: NormalizedDocument, *, minimum: int = 0) -> list[TermExplanation]:
    del minimum
    return build_terminology_result(document, implicit_analysis_available=False).terms


def suggest_questions(document: NormalizedDocument, *, minimum: int = 5) -> list[SuggestedQuestion]:
    """Provide conservative deterministic questions only when source anchors exist."""

    candidates: list[SuggestedQuestion] = []
    for chunk in document.chunks:
        text = chunk.text.casefold()
        if any(marker in text for marker in ("có nghĩa vụ", "chịu trách nhiệm", "không được")):
            candidates.append(
                SuggestedQuestion(
                    question="Chủ thể nào có nghĩa vụ hoặc trách nhiệm theo quy định này?",
                    rationale="Cần xác định đúng chủ thể thực hiện nghĩa vụ được nêu trong tài liệu.",
                    citation_ids=[chunk.chunk_id],
                    rubric_score=3,
                )
            )
        if any(marker in text for marker in ("điều kiện", "thủ tục", "trình tự", "thời hạn")):
            candidates.append(
                SuggestedQuestion(
                    question="Điều kiện, thủ tục hoặc thời hạn áp dụng quy định là gì?",
                    rationale="Các điều kiện áp dụng quyết định trực tiếp phạm vi thực hiện quy định.",
                    citation_ids=[chunk.chunk_id],
                    rubric_score=3,
                )
            )
        if len(candidates) >= minimum:
            break
    return candidates[:minimum]
