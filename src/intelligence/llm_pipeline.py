"""Fail-closed, hierarchical LLM generation for grounded meeting intelligence."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
import re
from typing import Iterable, Sequence

from pydantic import Field, model_validator

from ..integrations.llm import LlmClient, LlmClientError
from .contracts import (
    ContractModel,
    EvidenceItem,
    IntelligenceSummary,
    NormalizedDocument,
    SuggestedQuestion,
    TermCategory,
)
from .terminology import CandidateTerm


class EvidenceFinding(EvidenceItem):
    """A compact, source-grounded observation extracted from a document batch."""

    text: str = Field(min_length=1, max_length=360)
    kind: str = Field(min_length=1)


class LegalTermCandidate(ContractModel):
    """An evidence-bound legal concept proposed during an existing map call."""

    term: str = Field(min_length=1, max_length=180)
    category: TermCategory
    selection_reason: str = Field(min_length=1, max_length=240)
    legal_salience: int = Field(ge=0, le=100)
    reader_difficulty: int = Field(ge=0, le=100)
    citation_ids: list[str] = Field(min_length=1, max_length=2)
    explanation: str = Field(min_length=1, max_length=360)


class MapBatch(ContractModel):
    findings: list[EvidenceFinding] = Field(min_length=1, max_length=6)
    # Strict Structured Outputs requires every object key to be required. The model
    # emits [] when a batch has no qualified term, rather than omitting this field.
    term_candidates: list[LegalTermCandidate] = Field(max_length=4)

    @model_validator(mode="before")
    @classmethod
    def default_legacy_term_candidates(cls, value: object) -> object:
        """Accept legacy test/provider payloads while advertising a strict required key."""

        if isinstance(value, dict):
            return {"term_candidates": [], **value}
        return value


class StrictIntelligenceSummary(ContractModel):
    """Response-only schema: strict Structured Outputs requires every key."""

    context: list[EvidenceItem] = Field(min_length=1, max_length=3)
    main_content: list[EvidenceItem] = Field(min_length=1, max_length=3)
    decision_points: list[EvidenceItem] = Field(min_length=1, max_length=3)
    impact: list[EvidenceItem] = Field(min_length=1, max_length=3)


class ReducedSummary(ContractModel):
    summary: StrictIntelligenceSummary


class GeneratedQuestion(ContractModel):
    """Response-only schema without optional scoring metadata."""

    question: str = Field(min_length=1, max_length=300)
    rationale: str = Field(min_length=1, max_length=300)
    citation_ids: list[str] = Field(min_length=1)


class CriticalQuestions(ContractModel):
    suggested_questions: list[GeneratedQuestion] = Field(min_length=5, max_length=5)


class IntelligenceQualityError(LlmClientError):
    """Raised when otherwise valid JSON does not meet product quality requirements."""


@dataclass(frozen=True)
class LlmPipelineSettings:
    map_batch_chars: int = 18_000
    map_concurrency: int = 3

    @classmethod
    def from_env(cls) -> "LlmPipelineSettings":
        return cls(
            map_batch_chars=max(2_000, int(os.getenv("LLM_MAP_BATCH_CHARS", "18000"))),
            map_concurrency=max(1, min(3, int(os.getenv("LLM_MAP_CONCURRENCY", "3")))),
        )


@dataclass(frozen=True)
class LlmIntelligenceResult:
    summary: IntelligenceSummary
    suggested_questions: list[SuggestedQuestion]
    map_batch_count: int
    term_candidates: list[CandidateTerm]


class LlmIntelligencePipeline:
    """Extract all document evidence, then synthesize a grounded meeting report."""

    def __init__(self, client: LlmClient, settings: LlmPipelineSettings | None = None) -> None:
        self._client = client
        self._settings = settings or LlmPipelineSettings.from_env()

    async def generate(self, document: NormalizedDocument) -> LlmIntelligenceResult:
        batches = list(self._batches(document.chunks))
        if not batches:
            raise IntelligenceQualityError("Document has no usable text chunks for LLM generation.")

        semaphore = asyncio.Semaphore(self._settings.map_concurrency)

        async def run_batch(batch: list) -> MapBatch:
            async with semaphore:
                return await self._map_batch(batch)

        mapped_batches = await asyncio.gather(*(run_batch(batch) for batch in batches))
        findings = [finding for mapped in mapped_batches for finding in mapped.findings]
        if not findings:
            raise IntelligenceQualityError("LLM map stage returned no grounded findings.")

        summary = await self._reduce_summary(findings)
        questions = await self._generate_questions(summary, findings)
        self._validate_summary(summary)
        self._validate_questions(questions)
        return LlmIntelligenceResult(
            summary=summary,
            suggested_questions=questions,
            map_batch_count=len(batches),
            term_candidates=[
                CandidateTerm(
                    term=item.term,
                    category=item.category,
                    selection_reason=item.selection_reason,
                    legal_salience=item.legal_salience,
                    reader_difficulty=item.reader_difficulty,
                    citation_ids=item.citation_ids,
                    explanation=item.explanation,
                )
                for mapped in mapped_batches
                for item in mapped.term_candidates
            ],
        )

    def _batches(self, chunks: Sequence) -> Iterable[list]:
        batch: list = []
        size = 0
        for chunk in chunks:
            chunk_size = len(chunk.text) + len(chunk.chunk_id) + 8
            if batch and size + chunk_size > self._settings.map_batch_chars:
                yield batch
                batch, size = [], 0
            batch.append(chunk)
            size += chunk_size
        if batch:
            yield batch

    async def _map_batch(self, chunks: list) -> MapBatch:
        allowed_ids = {chunk.chunk_id for chunk in chunks}
        evidence = "\n".join(f"[{chunk.chunk_id}] {chunk.text}" for chunk in chunks)
        mapped = await self._client.call(
            [
                {
                    "role": "system",
                    "content": (
                        "You are extracting meeting intelligence from Vietnamese source text. "
                        "Return 1–6 concise, non-duplicated findings. Cover material topics, actors, "
                        "obligations, proposed choices, risks, timelines, conditions, and trade-offs when present. "
                        "Use kind values such as context, main_content, decision, impact, obligation, risk, "
                        "timeline, or tradeoff. Do not invent facts. Every finding must cite only its direct source IDs."
                        " Also return zero to four term_candidates (use [] when none qualify). A term candidate must be an exact phrase in "
                        "the supplied source and must be a legally specialized subject, right/obligation, procedure, "
                        "sanction/dispute, or technical concept; never return document titles, agencies, or generic nouns. "
                        "For each candidate use exactly one category: defined_term, legal_subject, "
                        "right_obligation, procedure_condition, sanction_dispute, or technical_concept; then provide "
                        "selection_reason, legal_salience 0-100, "
                        "reader_difficulty 0-100, a concise evidence-bound explanation, and direct citation IDs."
                    ),
                },
                {"role": "user", "content": f"Allowed citation IDs: {sorted(allowed_ids)}\n\nSource text:\n{evidence}"},
            ],
            MapBatch,
        )
        findings = [self._sanitize_item(item, allowed_ids, "map finding") for item in mapped.findings]
        terms = self._sanitize_term_candidates(mapped.term_candidates, allowed_ids)
        return mapped.model_copy(update={"findings": findings, "term_candidates": terms})

    @staticmethod
    def _sanitize_term_candidates(
        candidates: list[LegalTermCandidate], allowed_ids: set[str]
    ) -> list[LegalTermCandidate]:
        sanitized: list[LegalTermCandidate] = []
        for candidate in candidates:
            citations = list(dict.fromkeys(cid for cid in candidate.citation_ids if cid in allowed_ids))
            term = " ".join(candidate.term.split())
            explanation = " ".join(candidate.explanation.split())
            reason = " ".join(candidate.selection_reason.split())
            if not citations or not term or not explanation or not reason:
                continue
            sanitized.append(candidate.model_copy(update={
                "term": term,
                "explanation": explanation,
                "selection_reason": reason,
                "citation_ids": citations,
            }))
        return sanitized

    async def _reduce_summary(self, findings: list[EvidenceFinding]) -> IntelligenceSummary:
        allowed_ids = {citation_id for finding in findings for citation_id in finding.citation_ids}
        compact_findings = "\n".join(
            f"[{','.join(finding.citation_ids)}] ({finding.kind}) {finding.text}" for finding in findings
        )
        reduced = await self._client.call(
            [
                {
                    "role": "system",
                    "content": (
                        "Create an executive Vietnamese synthesis from the supplied findings. "
                        "Populate all four sections: context, main_content, decision_points, impact. "
                        "Each section must contain at least one concise paraphrase of the whole document's meaning, "
                        "not copied source excerpts. Decision points must identify actual choices, approvals, "
                        "or matters requiring clarification; impact must name concrete consequences, owners, or risks. "
                        "Every item must cite only IDs supplied with the findings."
                    ),
                },
                {"role": "user", "content": f"Allowed citation IDs: {sorted(allowed_ids)}\n\nFindings:\n{compact_findings}"},
            ],
            ReducedSummary,
        )
        return IntelligenceSummary(
            **{
                field: [self._sanitize_item(item, allowed_ids, f"summary.{field}") for item in getattr(reduced.summary, field)]
                for field in ("context", "main_content", "decision_points", "impact")
            }
        )

    async def _generate_questions(
        self,
        summary: IntelligenceSummary,
        findings: list[EvidenceFinding],
    ) -> list[SuggestedQuestion]:
        allowed_ids = {citation_id for finding in findings for citation_id in finding.citation_ids}
        summary_text = "\n".join(
            f"{field}: " + " | ".join(f"[{','.join(item.citation_ids)}] {item.text}" for item in getattr(summary, field))
            for field in ("context", "main_content", "decision_points", "impact")
        )
        evidence_text = "\n".join(
            f"[{','.join(finding.citation_ids)}] ({finding.kind}) {finding.text}" for finding in findings
        )
        drafted = await self._client.call(
            [
                {
                    "role": "system",
                    "content": (
                        "Write exactly five distinct, deep Vietnamese critical questions for a decision meeting. "
                        "Each must directly test a document-specific condition, owner, implementation capacity, "
                        "timeline, risk, legal basis, dependency, metric, or trade-off. Avoid generic questions such as "
                        "'đã đủ rõ chưa?' or 'ai chịu tác động?'. Rationale must explain why this exact issue matters. "
                        "Each question and rationale must cite only the supplied source IDs."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Allowed citation IDs: {sorted(allowed_ids)}\n\nExecutive synthesis:\n{summary_text}\n\nEvidence:\n{evidence_text}",
                },
            ],
            CriticalQuestions,
        )
        return [self._sanitize_question(item, allowed_ids) for item in drafted.suggested_questions]

    @staticmethod
    def _sanitize_item(item: EvidenceItem, allowed_ids: set[str], label: str) -> EvidenceItem:
        citations = list(dict.fromkeys(citation_id for citation_id in item.citation_ids if citation_id in allowed_ids))
        if not citations:
            raise IntelligenceQualityError(f"{label} has no valid citation IDs.")
        text = " ".join(item.text.split())
        if not text:
            raise IntelligenceQualityError(f"{label} has empty text.")
        return item.model_copy(update={"text": text, "citation_ids": citations})

    @classmethod
    def _sanitize_question(cls, item: GeneratedQuestion, allowed_ids: set[str]) -> SuggestedQuestion:
        citations = list(dict.fromkeys(citation_id for citation_id in item.citation_ids if citation_id in allowed_ids))
        if not citations:
            raise IntelligenceQualityError("suggested question has no valid citation IDs.")
        question = " ".join(item.question.split())
        rationale = " ".join(item.rationale.split())
        if not question or not rationale:
            raise IntelligenceQualityError("suggested question has empty question or rationale.")
        return SuggestedQuestion(question=question, rationale=rationale, citation_ids=citations)

    @staticmethod
    def _validate_summary(summary: IntelligenceSummary) -> None:
        for field in ("context", "main_content", "decision_points", "impact"):
            items = getattr(summary, field)
            if not items:
                raise IntelligenceQualityError(f"summary.{field} is empty.")
            normalized = [" ".join(item.text.casefold().split()) for item in items]
            if len(normalized) != len(set(normalized)):
                raise IntelligenceQualityError(f"summary.{field} contains duplicate statements.")

    @staticmethod
    def _validate_questions(questions: list[SuggestedQuestion]) -> None:
        if len(questions) != 5:
            raise IntelligenceQualityError("Exactly five suggested questions are required.")
        normalized = [re.sub(r"\W+", "", item.question.casefold()) for item in questions]
        if len(normalized) != len(set(normalized)) or any(not value for value in normalized):
            raise IntelligenceQualityError("Suggested questions must be non-empty and unique.")
