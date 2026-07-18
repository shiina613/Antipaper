"""Async, grounded map-reduce implementation for meeting intelligence."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
import inspect
import json
import re
from time import perf_counter
from typing import Any, TypeAlias

from .contracts import (
    EvidenceItem,
    IntelligenceDraft,
    IntelligenceReport,
    IntelligenceSummary,
    NormalizedDocument,
    QualityResult,
    StageTiming,
    SuggestedQuestion,
    TermExplanation,
    coerce_normalized_document,
)
from .prompts import MAP_PROMPT, REDUCE_PROMPT, SYSTEM_PROMPT


CallLLM: TypeAlias = Callable[[list[dict[str, str]], type[IntelligenceDraft]], Awaitable[Any]]
CitationValidator: TypeAlias = Callable[[list[str], NormalizedDocument], Any]


class IntelligenceConfigurationError(RuntimeError):
    """Raised when orchestration has not injected the shared LLM client."""


class IntelligenceGenerationError(RuntimeError):
    """Raised when no map result can be validated."""


class IntelligenceBuilder:
    """Generate a report in 6--8-page batches and enforce source grounding.

    ``call_llm`` is the shared client owned by ingestion/orchestration.  The
    builder does not initialize another model client and therefore remains
    deterministic under a test double.
    """

    def __init__(
        self,
        call_llm: CallLLM,
        *,
        citation_validator: CitationValidator | None = None,
        batch_pages: int = 7,
        max_concurrency: int = 3,
    ) -> None:
        if not 6 <= batch_pages <= 8:
            raise ValueError("batch_pages must be between 6 and 8")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self.call_llm = call_llm
        self.citation_validator = citation_validator
        self.batch_pages = batch_pages
        self.max_concurrency = max_concurrency

    async def build(self, document: NormalizedDocument | Any) -> IntelligenceReport:
        normalized = coerce_normalized_document(document)
        if not normalized.chunks:
            return self._empty_report()

        batches = self._build_batches(normalized)
        map_start = perf_counter()
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def map_one(index: int, chunks: list[dict[str, Any]]) -> IntelligenceDraft:
            pages = [int(chunk["page"]) for chunk in chunks]
            prompt = MAP_PROMPT.format(
                batch_number=index + 1,
                batch_count=len(batches),
                first_page=min(pages),
                last_page=max(pages),
                chunks_json=json.dumps(chunks, ensure_ascii=False),
            )
            async with semaphore:
                return await self._invoke_llm(prompt)

        map_results = await asyncio.gather(
            *(map_one(index, chunks) for index, chunks in enumerate(batches)),
            return_exceptions=True,
        )
        valid_maps = [result for result in map_results if isinstance(result, IntelligenceDraft)]
        if not valid_maps:
            errors = [str(result) for result in map_results if isinstance(result, BaseException)]
            raise IntelligenceGenerationError(
                "No map batch returned valid structured output"
                + (f": {'; '.join(errors)}" if errors else "")
            )
        timings = [
            StageTiming(
                stage="map",
                duration_ms=(perf_counter() - map_start) * 1000,
                llm_calls=len(batches),
            )
        ]

        reduce_start = perf_counter()
        reduce_prompt = REDUCE_PROMPT.format(
            drafts_json=json.dumps(
                [draft.model_dump(mode="json") for draft in valid_maps],
                ensure_ascii=False,
            )
        )
        reduced = await self._invoke_llm(reduce_prompt)
        timings.append(
            StageTiming(
                stage="reduce",
                duration_ms=(perf_counter() - reduce_start) * 1000,
                llm_calls=1,
            )
        )

        validation_start = perf_counter()
        sanitized, citations_valid = await self._sanitize(reduced, normalized)
        questions = [
            question.model_copy(
                update={"rubric_score": self._score_question(question, normalized)}
            )
            for question in sanitized.suggested_questions
        ]
        sanitized = sanitized.model_copy(update={"suggested_questions": questions})
        quality = self._quality(sanitized, citations_valid)
        timings.append(
            StageTiming(
                stage="validation",
                duration_ms=(perf_counter() - validation_start) * 1000,
                llm_calls=0,
            )
        )
        return IntelligenceReport(
            **sanitized.model_dump(),
            stage_timings=timings,
            quality=quality,
        )

    async def _invoke_llm(self, user_prompt: str) -> IntelligenceDraft:
        response = await self.call_llm(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            IntelligenceDraft,
        )
        if isinstance(response, IntelligenceDraft):
            return response
        if hasattr(response, "model_dump"):
            response = response.model_dump()
        return IntelligenceDraft.model_validate(response)

    def _build_batches(self, document: NormalizedDocument) -> list[list[dict[str, Any]]]:
        page_groups: dict[int, list[dict[str, Any]]] = {}
        for chunk in document.chunks:
            page_groups.setdefault(chunk.page, []).append(chunk.model_dump(mode="json"))

        batches: list[list[dict[str, Any]]] = []
        for first_page in range(1, document.page_count + 1, self.batch_pages):
            selected_pages = range(
                first_page,
                min(first_page + self.batch_pages, document.page_count + 1),
            )
            batch = [chunk for page in selected_pages for chunk in page_groups.get(page, [])]
            if batch:
                batches.append(batch)
        return batches

    async def _sanitize(
        self,
        draft: IntelligenceDraft,
        document: NormalizedDocument,
    ) -> tuple[IntelligenceDraft, bool]:
        whitelist = set(document.citation_whitelist)
        supplied_ids = self._all_citation_ids(draft)
        valid_ids = whitelist
        if self.citation_validator is not None and supplied_ids:
            validated = self.citation_validator(sorted(supplied_ids), document)
            if inspect.isawaitable(validated):
                validated = await validated
            external_ids = self._extract_validated_ids(validated)
            valid_ids = whitelist.intersection(external_ids)

        citations_valid = supplied_ids.issubset(valid_ids)

        def evidence(items: Iterable[EvidenceItem]) -> list[EvidenceItem]:
            result: list[EvidenceItem] = []
            seen: set[str] = set()
            for item in items:
                ids = [item_id for item_id in item.citation_ids if item_id in valid_ids]
                key = self._normalize_text(item.text)
                if not ids or key in seen:
                    continue
                seen.add(key)
                result.append(item.model_copy(update={"citation_ids": ids}))
            return result

        summary = IntelligenceSummary(
            context=evidence(draft.summary.context),
            main_content=evidence(draft.summary.main_content),
            decision_points=evidence(draft.summary.decision_points),
            impact=evidence(draft.summary.impact),
        )

        terms: list[TermExplanation] = []
        seen_terms: set[str] = set()
        for term in draft.terms:
            ids = [item_id for item_id in term.citation_ids if item_id in valid_ids]
            key = self._normalize_text(term.term)
            if not ids or key in seen_terms:
                continue
            seen_terms.add(key)
            terms.append(term.model_copy(update={"citation_ids": ids}))

        questions: list[SuggestedQuestion] = []
        for question in draft.suggested_questions:
            ids = [item_id for item_id in question.citation_ids if item_id in valid_ids]
            if not ids or self._is_duplicate_question(question.question, questions):
                continue
            questions.append(question.model_copy(update={"citation_ids": ids}))

        return IntelligenceDraft(
            summary=summary,
            terms=terms,
            suggested_questions=questions,
        ), citations_valid

    @staticmethod
    def _all_citation_ids(draft: IntelligenceDraft) -> set[str]:
        ids: set[str] = set()
        for section in (
            draft.summary.context,
            draft.summary.main_content,
            draft.summary.decision_points,
            draft.summary.impact,
        ):
            ids.update(item_id for item in section for item_id in item.citation_ids)
        ids.update(item_id for term in draft.terms for item_id in term.citation_ids)
        ids.update(
            item_id
            for question in draft.suggested_questions
            for item_id in question.citation_ids
        )
        return ids

    @staticmethod
    def _extract_validated_ids(values: Any) -> set[str]:
        if values is None:
            return set()
        result: set[str] = set()
        for value in values:
            if isinstance(value, str):
                result.add(value)
                continue
            if isinstance(value, dict):
                candidate = value.get("chunk_id") or value.get("citation_id") or value.get("id")
            else:
                candidate = (
                    getattr(value, "chunk_id", None)
                    or getattr(value, "citation_id", None)
                    or getattr(value, "id", None)
                )
            if candidate:
                result.add(str(candidate))
        return result

    def _score_question(
        self,
        question: SuggestedQuestion,
        document: NormalizedDocument,
    ) -> int:
        text = f"{question.question} {question.rationale}".lower()
        cited_text = " ".join(
            chunk.text.lower()
            for chunk in document.chunks
            if chunk.chunk_id in question.citation_ids
        )
        question_tokens = self._meaningful_tokens(text)
        evidence_tokens = self._meaningful_tokens(cited_text)
        specific = bool(question_tokens.intersection(evidence_tokens))
        drives_decision = any(
            keyword in text
            for keyword in (
                "quyết định",
                "trách nhiệm",
                "rủi ro",
                "tác động",
                "nguồn lực",
                "tiến độ",
                "căn cứ",
            )
        )
        meeting_ready = question.question.endswith("?") and 20 <= len(question.question) <= 300
        grounded = bool(question.citation_ids)
        return sum((specific, drives_decision, meeting_ready, grounded))

    @staticmethod
    def _quality(draft: IntelligenceDraft, citations_valid: bool) -> QualityResult:
        required_summary_complete = all(
            (
                draft.summary.context,
                draft.summary.main_content,
                draft.summary.decision_points,
                draft.summary.impact,
            )
        )
        passing = sum(
            (question.rubric_score or 0) >= 3
            for question in draft.suggested_questions
        )
        passed = (
            required_summary_complete
            and len(draft.terms) >= 10
            and len(draft.suggested_questions) >= 5
            and passing >= 5
            and citations_valid
        )
        return QualityResult(
            required_summary_complete=required_summary_complete,
            term_count=len(draft.terms),
            question_count=len(draft.suggested_questions),
            questions_passing_rubric=passing,
            citations_valid=citations_valid,
            passed=passed,
        )

    @staticmethod
    def _empty_report() -> IntelligenceReport:
        return IntelligenceReport(
            summary=IntelligenceSummary(),
            terms=[],
            suggested_questions=[],
            stage_timings=[],
            quality=QualityResult(
                required_summary_complete=False,
                term_count=0,
                question_count=0,
                questions_passing_rubric=0,
                citations_valid=True,
                passed=False,
            ),
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(re.findall(r"[\wÀ-ỹ]+", text.casefold()))

    @classmethod
    def _meaningful_tokens(cls, text: str) -> set[str]:
        return {token for token in cls._normalize_text(text).split() if len(token) >= 5}

    @classmethod
    def _is_duplicate_question(
        cls,
        candidate: str,
        existing: Iterable[SuggestedQuestion],
    ) -> bool:
        candidate_tokens = cls._meaningful_tokens(candidate)
        for question in existing:
            existing_tokens = cls._meaningful_tokens(question.question)
            union = candidate_tokens.union(existing_tokens)
            if union and len(candidate_tokens.intersection(existing_tokens)) / len(union) >= 0.72:
                return True
        return False


async def build_intelligence(
    document: NormalizedDocument | Any,
    *,
    call_llm: CallLLM | None = None,
    citation_validator: CitationValidator | None = None,
    batch_pages: int = 7,
) -> IntelligenceReport:
    """Handoff function; inject the team's shared LLM client.

    No implicit external client is constructed.  This prevents configuration,
    retry, and cost behavior from diverging between pipeline components.
    """

    if call_llm is None:
        raise IntelligenceConfigurationError(
            "build_intelligence requires the shared call_llm implementation"
        )
    return await IntelligenceBuilder(
        call_llm,
        citation_validator=citation_validator,
        batch_pages=batch_pages,
    ).build(document)
