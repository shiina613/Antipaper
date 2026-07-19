"""Deterministic document orchestration for the no-cache runtime."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import os
import time
from typing import Any, Callable

from ..ingestion import DocumentIngestor, IngestionError, StitchedPage
from ..integrations.llm import LlmClient, LlmClientError, LlmClientTimeoutError, LlmSettings
from ..intelligence import (
    LlmIntelligencePipeline,
    NormalizedDocument,
    ProcessingDeadlineExceeded,
    build_local_intelligence_pack,
    build_terminology_result,
)
from ..retrieval import GroundedQAService, RetrievalIndex, build_index
from ..schemas import (
    Citation,
    DocumentReport,
    DocumentSummary,
    PageBlock,
    QuestionResponse,
    ReportQuality,
    SuggestedQuestion,
    StageTiming,
    SummaryItem,
    TermItem,
    TerminologyQuality,
)


logger = logging.getLogger(__name__)
MAX_ANALYZABLE_TEXT_CHARS = int(os.getenv("MAX_ANALYZABLE_TEXT_CHARS", "600000"))
DEFAULT_PROCESSING_DEADLINE_SECONDS = float(os.getenv("PROCESSING_DEADLINE_SECONDS", "110"))
# Native PDF/DOCX extraction is CPU-bound and scales with page count, scanned images, and
# concurrent load, so a large-but-healthy document can parse in ~5s alone yet 11-14s while
# several workers share the GIL. Guard against ingestion eating the whole budget, but do it
# with a configurable ceiling (bounded by the total deadline) instead of a flat magic number.
INGESTION_DEADLINE_SECONDS = float(os.getenv("INGESTION_DEADLINE_SECONDS", "45"))


class AnalysisTextLimitExceeded(IngestionError):
    """Raised before LLM work when extracted content exceeds the supported SLA envelope."""


@dataclass
class ProcessedDocument:
    source_name: str
    page_count: int
    stitched_pages: list[StitchedPage]
    normalized_document: NormalizedDocument
    processing_seconds: float = 0.0
    chunks: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class OrchestrationResult:
    processed_document: ProcessedDocument
    normalized_document: NormalizedDocument
    report: DocumentReport


@dataclass(frozen=True)
class QuestionTrace:
    response: QuestionResponse
    retrieved_ids: tuple[str, ...]
    retrieval_context: tuple[str, ...]
    retrieval_scores: tuple[float, ...]


class DocumentOrchestrator:
    """One flow: upload bytes -> native extraction -> lexical index -> report."""

    def __init__(
        self,
        *,
        ingestor: DocumentIngestor | None = None,
        llm: LlmClient | None = None,
        use_configured_llm: bool = True,
    ) -> None:
        self._ingestor = ingestor or DocumentIngestor()
        self._llm = llm if llm is not None else (self._configured_llm() if use_configured_llm else None)

    @property
    def llm_enabled(self) -> bool:
        return self._llm is not None

    def process(
        self,
        *,
        document_id: str,
        file_name: str,
        file_bytes: bytes,
        deadline_seconds: float = DEFAULT_PROCESSING_DEADLINE_SECONDS,
        stage_callback: Callable[[str], None] | None = None,
    ) -> OrchestrationResult:
        started = time.perf_counter()
        normalized, pages = self.ingest(document_id=document_id, file_name=file_name, file_bytes=file_bytes)
        input_characters = sum(len(chunk.text) for chunk in normalized.chunks)
        if input_characters > MAX_ANALYZABLE_TEXT_CHARS:
            raise AnalysisTextLimitExceeded(
                f"Extracted text has {input_characters:,} characters; the analysis limit is "
                f"{MAX_ANALYZABLE_TEXT_CHARS:,} characters."
            )
        elapsed = time.perf_counter() - started
        ingestion_budget = min(INGESTION_DEADLINE_SECONDS, deadline_seconds)
        if ingestion_budget > 0 and elapsed > ingestion_budget:
            raise ProcessingDeadlineExceeded(
                f"Processing deadline exceeded during ingestion (took {elapsed:.1f}s, budget {ingestion_budget:.0f}s)."
            )
        processed = ProcessedDocument(
            source_name=file_name,
            page_count=normalized.page_count,
            stitched_pages=pages,
            normalized_document=normalized,
            chunks=list(normalized.chunks),
        )
        report = asyncio.run(
            self._report(
                normalized,
                deadline_seconds=max(0.0, deadline_seconds - elapsed),
                stage_callback=stage_callback,
            )
        )
        report = report.model_copy(
            update={
                "quality": report.quality.model_copy(
                    update={
                        "input_characters": input_characters,
                        "stage_timings": [
                            StageTiming(stage="ingestion", duration_ms=round(elapsed * 1000, 3)),
                            *report.quality.stage_timings,
                        ],
                    }
                )
            }
        )
        return OrchestrationResult(processed, normalized, report)

    def ingest(
        self,
        *,
        document_id: str,
        file_name: str,
        file_bytes: bytes,
    ) -> tuple[NormalizedDocument, list[StitchedPage]]:
        try:
            return self._ingestor.ingest_bytes(
                file_name=file_name,
                file_bytes=file_bytes,
                document_id=document_id,
            )
        except IngestionError:
            raise

    def build_retrieval_index(self, document: NormalizedDocument) -> RetrievalIndex:
        return build_index(document)

    async def answer_question_async(
        self,
        processed_document: ProcessedDocument,
        question: str,
        retrieval_index: RetrievalIndex | None = None,
    ) -> QuestionTrace:
        index = retrieval_index or build_index(processed_document.normalized_document)
        answer = await GroundedQAService(index).answer(question, top_k=5)
        by_id = {chunk.chunk_id: chunk for chunk in index.chunks}
        selected = [by_id[item_id] for item_id in answer.retrieved_ids if item_id in by_id]
        response = QuestionResponse(
            answer=answer.answer,
            insufficient_evidence=answer.insufficient_evidence,
            citation_ids=answer.citation_ids,
            latency_ms=answer.latency_ms,
        )
        return QuestionTrace(
            response=response,
            retrieved_ids=tuple(chunk.chunk_id for chunk in selected),
            retrieval_context=tuple(chunk.text for chunk in selected),
            retrieval_scores=tuple(0.0 for _ in selected),
        )

    def to_page_blocks(self, processed_document: ProcessedDocument) -> list[PageBlock]:
        return [PageBlock(kind="text", text=page.content, page_number=page.page_number) for page in processed_document.stitched_pages]

    async def _report(
        self,
        document: NormalizedDocument,
        *,
        deadline_seconds: float,
        stage_callback: Callable[[str], None] | None,
    ) -> DocumentReport:
        """Generate with the model when possible, while preserving a grounded partial report on failure."""

        if self._llm is None:
            return self._partial_report(document, warning="LLM_NOT_CONFIGURED")
        try:
            return await self._llm_report(
                document,
                deadline_seconds=deadline_seconds,
                stage_callback=stage_callback,
            )
        except ProcessingDeadlineExceeded:
            raise
        except LlmClientTimeoutError:
            raise
        except LlmClientError as exc:
            # No model text is logged or returned to the browser: source content can be sensitive.
            logger.warning("llm_report_fallback document_id=%s error=%s", document.document_id, type(exc).__name__)
            return self._partial_report(document, warning="LLM_GENERATION_FAILED")

    async def _llm_report(
        self,
        document: NormalizedDocument,
        *,
        deadline_seconds: float,
        stage_callback: Callable[[str], None] | None,
    ) -> DocumentReport:
        if self._llm is None:
            raise RuntimeError("_llm_report requires an LLM client")
        generated = await LlmIntelligencePipeline(self._llm).generate(
            document,
            deadline_seconds=deadline_seconds,
            stage_callback=stage_callback,
        )
        terminology = build_terminology_result(
            document,
            generated.term_candidates,
            implicit_analysis_available=True,
        )
        terminology_quality = self._terminology_quality(terminology)
        report_status = "complete" if terminology.status == "complete" else "partial"
        citations = {
            chunk_id: Citation(
                page=value.page,
                chapter=value.chapter,
                article=value.article,
                clause=value.clause,
                excerpt=value.excerpt,
            )
            for chunk_id, value in document.citations.items()
        }
        return DocumentReport(
            document_id=document.document_id,
            file_name=document.file_name,
            page_count=document.page_count,
            processing_seconds=0.0,
            summary=DocumentSummary(
                **{
                    field: [SummaryItem(text=item.text, citation_ids=item.citation_ids) for item in getattr(generated.summary, field)]
                    for field in ("context", "main_content", "decision_points", "impact")
                }
            ),
            terms=[self._term_item(item) for item in terminology.terms],
            suggested_questions=[
                SuggestedQuestion(question=item.question, rationale=item.rationale, citation_ids=item.citation_ids)
                for item in generated.suggested_questions
            ],
            citations=citations,
            generation_mode="llm",
            quality=ReportQuality(
                pipeline="llm_map_reduce",
                map_batch_count=generated.map_batch_count,
                question_count=len(generated.suggested_questions),
                summary_sections_complete=True,
                citations_valid=True,
                report_status=report_status,
                passed=report_status == "complete",
                terminology=terminology_quality,
                map_wave_count=generated.map_wave_count,
                llm_call_count=generated.llm_call_count,
                retry_count=generated.retry_count,
                queue_ms=generated.queue_ms,
                stage_timings=[StageTiming(stage=stage, duration_ms=duration_ms) for stage, duration_ms in generated.stage_timings],
            ),
        )

    def _partial_report(self, document: NormalizedDocument, *, warning: str) -> DocumentReport:
        """Return only deterministic, citation-backed data when model generation is unavailable."""

        terminology = build_terminology_result(
            document,
            implicit_analysis_available=False,
            warnings=[warning],
        )
        pack = build_local_intelligence_pack(document, minimum_questions=5)
        summary = self._deterministic_summary(document)
        return DocumentReport(
            document_id=document.document_id,
            file_name=document.file_name,
            page_count=document.page_count,
            processing_seconds=0.0,
            summary=summary,
            terms=[self._term_item(item) for item in terminology.terms],
            suggested_questions=[
                SuggestedQuestion(question=item.question, rationale=item.rationale, citation_ids=item.citation_ids)
                for item in pack.suggested_questions
            ],
            citations=self._citations(document),
            generation_mode="terminology_partial",
            quality=ReportQuality(
                pipeline="deterministic_fallback",
                map_batch_count=0,
                question_count=len(pack.suggested_questions),
                summary_sections_complete=all(
                    getattr(summary, field)
                    for field in ("context", "main_content", "decision_points", "impact")
                ),
                citations_valid=True,
                report_status="partial",
                passed=False,
                terminology=self._terminology_quality(terminology),
            ),
        )

    @staticmethod
    def _citations(document: NormalizedDocument) -> dict[str, Citation]:
        return {
            chunk_id: Citation(
                page=value.page,
                chapter=value.chapter,
                article=value.article,
                clause=value.clause,
                excerpt=value.excerpt,
            )
            for chunk_id, value in document.citations.items()
        }

    @staticmethod
    def _term_item(item: Any) -> TermItem:
        return TermItem(
            term=item.term,
            explanation=item.explanation,
            citation_ids=item.citation_ids,
            category=item.category,
            source_type=item.source_type,
            importance_reason=item.importance_reason,
            external_sources=item.external_sources,
        )

    @staticmethod
    def _terminology_quality(result: Any) -> TerminologyQuality:
        return TerminologyQuality(
            status=result.status,
            explicit_detected=result.explicit_detected,
            explicit_returned=result.explicit_returned,
            implicit_returned=result.implicit_returned,
            generic_rejected=result.generic_rejected,
            warnings=result.warnings,
        )

    @staticmethod
    def _deterministic_summary(document: NormalizedDocument) -> DocumentSummary:
        """Expose compact source excerpts; this path must never fabricate a summary."""

        def select(*needles: str, used: set[str]) -> SummaryItem | None:
            candidates = [
                chunk for chunk in document.chunks
                if chunk.chunk_id not in used and any(needle in chunk.text.casefold() for needle in needles)
            ]
            chunk = (candidates or [item for item in document.chunks if item.chunk_id not in used] or list(document.chunks))
            if not chunk:
                return None
            selected = chunk[0]
            used.add(selected.chunk_id)
            text = " ".join(selected.text.split())
            if len(text) > 700:
                text = text[:697].rstrip() + "..."
            return SummaryItem(text=text, citation_ids=[selected.chunk_id])

        used: set[str] = set()
        selections = {
            "context": select("căn cứ", "phạm vi", "điều", used=used),
            "main_content": select("quy định", "nghĩa vụ", "quyền", used=used),
            "decision_points": select("phê duyệt", "quyết định", "trách nhiệm", "thẩm quyền", used=used),
            "impact": select("xử phạt", "rủi ro", "hiệu lực", "vi phạm", used=used),
        }
        return DocumentSummary(**{key: [item] if item else [] for key, item in selections.items()})

    @staticmethod
    def _configured_llm() -> LlmClient | None:
        if not (os.getenv("LLM_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()):
            return None
        return LlmClient(LlmSettings.from_env())
