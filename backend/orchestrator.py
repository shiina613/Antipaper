"""Orchestrate ingestion, intelligence, and API contract mapping."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
from io import BytesIO
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import fitz

try:
    from ingestion import IngestionOptions, ingest_document
    from intelligence import (
        MeetingIntelligenceEngine,
        MeetingIntelligenceReport,
        NormalizedDocument,
        build_local_intelligence_pack,
    )
    from intelligence.contracts import Citation as ContractCitation
    from intelligence.contracts import DocumentChunk
    from retrieval import GroundedQAService, build_index, extract_related_documents
    from summary import DocumentSummaryEngine
except ModuleNotFoundError:  # Running backend from repo root without pytest PYTHONPATH.
    from src.ingestion import IngestionOptions, ingest_document
    from src.intelligence import (
        MeetingIntelligenceEngine,
        MeetingIntelligenceReport,
        NormalizedDocument,
        build_local_intelligence_pack,
    )
    from src.intelligence.contracts import Citation as ContractCitation
    from src.intelligence.contracts import DocumentChunk
    from src.retrieval import GroundedQAService, build_index, extract_related_documents
    from src.summary import DocumentSummaryEngine

from .schemas import (
    Citation,
    DocumentReport,
    DocumentSummary,
    PageBlock,
    QuestionResponse,
    RelatedDocument,
    SuggestedQuestion,
    SummaryItem,
    TermItem,
)


_WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_DEFAULT_SAMPLE_QUESTION = "What are the main points in this document?"


@dataclass(frozen=True)
class StitchedPage:
    page_number: int
    content: str


@dataclass
class ProcessedDocument:
    source_name: str
    page_count: int
    stitched_pages: list[StitchedPage]
    chunks: list = field(default_factory=list, repr=False, compare=False)
    processing_seconds: float = 0.0
    normalized_document: NormalizedDocument | None = field(
        default=None, repr=False, compare=False
    )

    @property
    def full_text(self) -> str:
        return "\n\n".join(
            f"[Trang {page.page_number}]\n{page.content}"
            for page in self.stitched_pages
            if page.content
        )


@dataclass(frozen=True)
class OrchestrationResult:
    processed_document: ProcessedDocument
    report: DocumentReport


class DocumentOrchestrator:
    """Translate uploaded bytes into processed documents and API responses."""

    def __init__(self) -> None:
        self._engine = MeetingIntelligenceEngine()
        self._summary_engine = DocumentSummaryEngine()

    def process(self, *, document_id: str, file_name: str, file_bytes: bytes) -> OrchestrationResult:
        processed_document = self._load_document(file_name=file_name, file_bytes=file_bytes)
        if processed_document.normalized_document is None:
            processed_document.normalized_document = self._normalized_from_pages(
                document_id=document_id,
                file_name=file_name,
                processed_document=processed_document,
            )
        if not processed_document.chunks:
            processed_document.chunks = self._engine.extract_chunks(processed_document)

        report = self._build_report(
            document_id=document_id,
            processed_document=processed_document,
            file_name=file_name,
        )
        return OrchestrationResult(processed_document=processed_document, report=report)

    def answer_question(self, processed_document: ProcessedDocument, question: str) -> QuestionResponse:
        normalized = processed_document.normalized_document
        if normalized is None:
            normalized = self._normalized_from_pages(
                document_id="runtime",
                file_name=processed_document.source_name,
                processed_document=processed_document,
            )
            processed_document.normalized_document = normalized

        answer = self._run_async(GroundedQAService(build_index(normalized)).answer(question))
        return QuestionResponse(
            answer=answer.answer,
            insufficient_evidence=bool(
                getattr(answer, "insufficient_evidence", False)
                or getattr(answer, "out_of_scope", False)
                or not answer.citation_ids
            ),
            citation_ids=list(answer.citation_ids or []),
            latency_ms=float(getattr(answer, "latency_ms", 0.0) or 0.0),
        )

    @staticmethod
    def _run_async(awaitable):
        """Run a coroutine from sync code, including inside FastAPI's event loop."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(awaitable)

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, awaitable).result()

    def to_page_blocks(self, processed_document: ProcessedDocument) -> list[PageBlock]:
        return [
            PageBlock(kind="text", text=page.content, page_number=page.page_number)
            for page in processed_document.stitched_pages
        ]

    def _load_document(self, *, file_name: str, file_bytes: bytes) -> ProcessedDocument:
        suffix = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        ingested = self._try_ingest_normalized(file_name=file_name, file_bytes=file_bytes, suffix=suffix)
        if ingested is not None:
            return ingested
        if suffix == ".pdf":
            return self._load_pdf_document(file_name=file_name, file_bytes=file_bytes)
        if suffix == ".docx":
            return self._load_docx_document(file_name=file_name, file_bytes=file_bytes)
        raise ValueError(f"Unsupported file type: {suffix or file_name}")

    def _try_ingest_normalized(
        self,
        *,
        file_name: str,
        file_bytes: bytes,
        suffix: str,
    ) -> ProcessedDocument | None:
        if suffix not in {".pdf", ".docx"}:
            return None
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                handle.write(file_bytes)
                temp_path = Path(handle.name)
            normalized = ingest_document(
                temp_path,
                IngestionOptions(use_yolo_tables=False, require_yolo_weights=False),
            )
            if not normalized.chunks:
                return None
            pages_by_number: dict[int, list[str]] = {}
            for chunk in normalized.chunks:
                pages_by_number.setdefault(chunk.page, []).append(chunk.text)
            stitched_pages = [
                StitchedPage(page_number=page, content="\n\n".join(parts).strip())
                for page, parts in sorted(pages_by_number.items())
            ]
            if not stitched_pages:
                stitched_pages = [StitchedPage(page_number=1, content="")]
            return ProcessedDocument(
                source_name=file_name,
                page_count=normalized.page_count,
                stitched_pages=stitched_pages,
                normalized_document=normalized.model_copy(
                    update={"document_id": normalized.document_id, "file_name": file_name}
                ),
            )
        except Exception:
            return None
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def _load_pdf_document(self, *, file_name: str, file_bytes: bytes) -> ProcessedDocument:
        try:
            return self._load_real_pdf_document(file_name=file_name, file_bytes=file_bytes)
        except Exception:
            return self._load_fallback_text_document(file_name=file_name, file_bytes=file_bytes)

    def _load_real_pdf_document(self, *, file_name: str, file_bytes: bytes) -> ProcessedDocument:
        stitched_pages: list[StitchedPage] = []
        with fitz.open(stream=file_bytes, filetype="pdf") as document:
            for page_index, page in enumerate(document):
                page_text = page.get_text("text").strip()
                if not page_text:
                    blocks = [
                        str(block[4]).strip()
                        for block in page.get_text("blocks", sort=True)
                        if str(block[4]).strip()
                    ]
                    page_text = "\n\n".join(blocks).strip()
                stitched_pages.append(StitchedPage(page_number=page_index + 1, content=page_text))

        if not stitched_pages:
            stitched_pages = [StitchedPage(page_number=1, content="")]

        return ProcessedDocument(
            source_name=file_name,
            page_count=len(stitched_pages),
            stitched_pages=stitched_pages,
        )

    def _load_fallback_text_document(self, *, file_name: str, file_bytes: bytes) -> ProcessedDocument:
        text = self._decode_fallback_bytes(file_bytes)
        return ProcessedDocument(
            source_name=file_name,
            page_count=1,
            stitched_pages=[StitchedPage(page_number=1, content=text)],
        )

    def _load_docx_document(self, *, file_name: str, file_bytes: bytes) -> ProcessedDocument:
        paragraphs = self._extract_docx_paragraphs(file_bytes)
        if not paragraphs:
            paragraphs = [""]

        page_size = max(1, len(paragraphs) // 6 or 1)
        stitched_pages: list[StitchedPage] = []
        for index in range(0, len(paragraphs), page_size):
            page_paragraphs = paragraphs[index : index + page_size]
            text = "\n\n".join(page_paragraphs).strip()
            stitched_pages.append(StitchedPage(page_number=len(stitched_pages) + 1, content=text))

        return ProcessedDocument(
            source_name=file_name,
            page_count=len(stitched_pages),
            stitched_pages=stitched_pages,
        )

    def _build_report(
        self,
        *,
        document_id: str,
        processed_document: ProcessedDocument,
        file_name: str,
    ) -> DocumentReport:
        normalized = processed_document.normalized_document
        if normalized is not None and normalized.chunks:
            return self._build_report_from_normalized(
                document_id=document_id,
                file_name=file_name,
                processed_document=processed_document,
                normalized=normalized,
            )
        return self._build_report_legacy(
            document_id=document_id,
            file_name=file_name,
            processed_document=processed_document,
        )

    def _build_report_from_normalized(
        self,
        *,
        document_id: str,
        file_name: str,
        processed_document: ProcessedDocument,
        normalized: NormalizedDocument,
    ) -> DocumentReport:
        summary_model = self._summary_engine.build(normalized)
        pack = build_local_intelligence_pack(normalized)
        related_hits = extract_related_documents(normalized)
        citation_map = {
            chunk_id: Citation(
                page=citation.page,
                chapter=citation.chapter,
                article=citation.article,
                clause=citation.clause,
                excerpt=citation.excerpt,
            )
            for chunk_id, citation in normalized.citations.items()
        }
        if not citation_map:
            citation_map = self._build_citation_map(processed_document)

        return DocumentReport(
            document_id=document_id,
            file_name=file_name,
            page_count=processed_document.page_count,
            processing_seconds=processed_document.processing_seconds,
            summary=DocumentSummary(
                context=[
                    SummaryItem(text=item.text, citation_ids=item.citation_ids)
                    for item in summary_model.context
                ],
                main_content=[
                    SummaryItem(text=item.text, citation_ids=item.citation_ids)
                    for item in summary_model.main_content
                ],
                decision_points=[
                    SummaryItem(text=item.text, citation_ids=item.citation_ids)
                    for item in summary_model.decision_points
                ],
                impact=[
                    SummaryItem(text=item.text, citation_ids=item.citation_ids)
                    for item in summary_model.impact
                ],
            ),
            terms=[
                TermItem(
                    term=term.term,
                    explanation=term.explanation,
                    citation_ids=term.citation_ids,
                )
                for term in pack.terms
            ],
            suggested_questions=[
                SuggestedQuestion(
                    question=question.question,
                    rationale=question.rationale,
                    citation_ids=question.citation_ids,
                )
                for question in pack.suggested_questions
            ],
            related_documents=[
                RelatedDocument(
                    title=item.title,
                    document_number=item.document_number,
                    source=item.source,
                    reason=item.reason,
                    citation_ids=item.citation_ids,
                )
                for item in related_hits
            ],
            citations=citation_map,
        )

    def _build_report_legacy(
        self,
        *,
        document_id: str,
        file_name: str,
        processed_document: ProcessedDocument,
    ) -> DocumentReport:
        intelligence: MeetingIntelligenceReport = self._engine.build_report(
            document=processed_document,
            sample_question=_DEFAULT_SAMPLE_QUESTION,
        )
        citation_map = self._build_citation_map(processed_document)
        summary = DocumentSummary(
            context=self._map_summary_items(intelligence.summary.context, citation_map, [1]),
            main_content=self._map_summary_items(
                intelligence.summary.main_content,
                citation_map,
                [1, min(2, processed_document.page_count)],
            ),
            decision_points=self._map_summary_items(
                intelligence.summary.decision_points,
                citation_map,
                [min(2, processed_document.page_count)],
            ),
            impact=self._map_summary_items(
                intelligence.summary.impact,
                citation_map,
                [min(3, processed_document.page_count)],
            ),
        )

        terms = [
            TermItem(
                term=term.term,
                explanation=term.explanation,
                citation_ids=self._pages_to_citation_ids(term.pages, citation_map),
            )
            for term in intelligence.terms
        ]

        suggested_questions = [
            SuggestedQuestion(
                question=question.question,
                rationale=question.rationale,
                citation_ids=self._pages_to_citation_ids(
                    self._pages_from_labels(question.citations),
                    citation_map,
                ),
            )
            for question in intelligence.questions
        ]

        normalized = processed_document.normalized_document
        related_documents = (
            [
                RelatedDocument(
                    title=item.title,
                    document_number=item.document_number,
                    source=item.source,
                    reason=item.reason,
                    citation_ids=item.citation_ids,
                )
                for item in extract_related_documents(normalized)
            ]
            if normalized is not None
            else self._build_related_documents_fallback(citation_map)
        )

        return DocumentReport(
            document_id=document_id,
            file_name=file_name,
            page_count=processed_document.page_count,
            processing_seconds=processed_document.processing_seconds,
            summary=summary,
            terms=terms,
            suggested_questions=suggested_questions,
            related_documents=related_documents,
            citations=citation_map,
        )

    def _build_related_documents_fallback(self, citation_map: dict[str, Citation]) -> list[RelatedDocument]:
        if not citation_map:
            return []
        first_id = next(iter(citation_map))
        return [
            RelatedDocument(
                title="Document source excerpt",
                document_number=f"PAGE-{citation_map[first_id].page}",
                source="cited_in_document",
                reason="Source evidence identified during processing.",
                citation_ids=[first_id],
            )
        ]

    def _normalized_from_pages(
        self,
        *,
        document_id: str,
        file_name: str,
        processed_document: ProcessedDocument,
    ) -> NormalizedDocument:
        chunks: list[DocumentChunk] = []
        citations: dict[str, ContractCitation] = {}
        for page in processed_document.stitched_pages:
            text = page.content.strip() or f"Trang {page.page_number} không có nội dung text."
            chunk_id = self._citation_id_for_page(page.page_number)
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    page=page.page_number,
                    text=text,
                )
            )
            citations[chunk_id] = ContractCitation(
                page=page.page_number,
                excerpt=self._shorten(text, 220),
            )
        return NormalizedDocument(
            document_id=document_id[:16] if len(document_id) > 16 else document_id,
            file_name=file_name or processed_document.source_name,
            page_count=max(processed_document.page_count, 1),
            chunks=chunks,
            citations=citations,
        )

    def _build_citation_map(self, processed_document: ProcessedDocument) -> dict[str, Citation]:
        citation_map: dict[str, Citation] = {}
        for page in processed_document.stitched_pages:
            citation_id = self._citation_id_for_page(page.page_number)
            citation_map[citation_id] = Citation(
                page=page.page_number,
                chapter=None,
                article=None,
                clause=None,
                excerpt=self._shorten(page.content, 240),
            )
        return citation_map

    def _map_summary_items(
        self,
        items: list[str],
        citation_map: dict[str, Citation],
        pages: list[int],
    ) -> list[SummaryItem]:
        citation_ids = self._pages_to_citation_ids(pages, citation_map)
        if not citation_ids and citation_map:
            citation_ids = [next(iter(citation_map))]
        return [
            SummaryItem(text=item, citation_ids=citation_ids[:1] if citation_ids else [])
            for item in items
        ]

    def _pages_to_citation_ids(self, pages: list[int], citation_map: dict[str, Citation]) -> list[str]:
        result: list[str] = []
        for page in pages:
            citation_id = self._citation_id_for_page(page)
            if citation_id in citation_map and citation_id not in result:
                result.append(citation_id)
        return result

    def _pages_from_labels(self, labels: list[str]) -> list[int]:
        pages: list[int] = []
        for label in labels:
            match = re.search(r"Trang\s+(\d+)", label)
            if match:
                pages.append(int(match.group(1)))
        return pages

    def _extract_docx_paragraphs(self, file_bytes: bytes) -> list[str]:
        paragraphs: list[str] = []
        with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
            with archive.open("word/document.xml") as stream:
                tree = ET.parse(stream)
        for paragraph in tree.findall(".//w:p", _WORD_NAMESPACE):
            parts = [node.text for node in paragraph.findall(".//w:t", _WORD_NAMESPACE) if node.text]
            text = "".join(parts).strip()
            if text:
                paragraphs.append(text)
        return paragraphs

    def _decode_fallback_bytes(self, file_bytes: bytes) -> str:
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                text = file_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
            compact = " ".join(text.split())
            if compact:
                return compact
        return f"Uploaded document hash {hashlib.sha256(file_bytes).hexdigest()[:12]}"

    def _citation_id_for_page(self, page_number: int) -> str:
        return f"P{page_number}-D1"

    def _shorten(self, text: str, limit: int = 180) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3].rstrip() + "..."
