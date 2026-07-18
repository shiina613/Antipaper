"""Orchestrate ingestion, intelligence, and API contract mapping."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
from io import BytesIO
import re
from typing import Any, Callable
import xml.etree.ElementTree as ET
import zipfile

import fitz
from pydantic import BaseModel

try:
    from intelligence import (
        Citation as DomainCitation,
        DocumentChunk,
        IntelligenceReport,
        MeetingIntelligenceEngine,
        MeetingIntelligenceReport,
        NormalizedDocument,
        build_intelligence,
    )
    from retrieval import GroundedQAService, RetrievalIndex, build_index
except ModuleNotFoundError:  # Running backend from repo root without pytest PYTHONPATH.
    from src.intelligence import (
        Citation as DomainCitation,
        DocumentChunk,
        IntelligenceReport,
        MeetingIntelligenceEngine,
        MeetingIntelligenceReport,
        NormalizedDocument,
        build_intelligence,
    )
    from src.retrieval import GroundedQAService, RetrievalIndex, build_index

from .llm import build_shared_llm_client
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
    chunks: list["_Chunk"] = field(default_factory=list, repr=False, compare=False)
    processing_seconds: float = 0.0

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
    normalized_document: NormalizedDocument
    report: DocumentReport


@dataclass(frozen=True)
class QuestionTrace:
    """Internal retrieval evidence used by evaluation, never serialized by the API."""

    response: QuestionResponse
    retrieved_ids: tuple[str, ...]
    retrieval_context: tuple[str, ...]
    retrieval_scores: tuple[float, ...]


class _QAOutput(BaseModel):
    answer: str
    citation_ids: list[str]


class DocumentOrchestrator:
    """Translate uploaded bytes into processed documents and API responses."""

    def __init__(
        self,
        *,
        call_llm: Callable[..., Any] | None = None,
        embedding: Callable[[str], Any] | None = None,
        use_configured_llm: bool = True,
    ) -> None:
        self._engine = MeetingIntelligenceEngine()
        self._call_llm = (
            call_llm
            if call_llm is not None
            else build_shared_llm_client() if use_configured_llm else None
        )
        self._embedding = embedding

    def process(self, *, document_id: str, file_name: str, file_bytes: bytes) -> OrchestrationResult:
        processed_document, normalized_document = self.ingest(
            document_id=document_id,
            file_name=file_name,
            file_bytes=file_bytes,
        )
        report = self._build_report(
            document_id=document_id,
            processed_document=processed_document,
            normalized_document=normalized_document,
            file_name=file_name,
        )
        return OrchestrationResult(
            processed_document=processed_document,
            normalized_document=normalized_document,
            report=report,
        )

    def ingest(
        self,
        *,
        document_id: str,
        file_name: str,
        file_bytes: bytes,
    ) -> tuple[ProcessedDocument, NormalizedDocument]:
        """Extract and normalize once for intelligence, retrieval, cache, and evals."""

        processed_document = self._load_document(file_name=file_name, file_bytes=file_bytes)
        if not processed_document.chunks:
            processed_document.chunks = self._engine.extract_chunks(processed_document)

        normalized_document = self._normalize_document(
            document_id=document_id,
            file_name=file_name,
            processed_document=processed_document,
        )
        return processed_document, normalized_document

    def build_retrieval_index(self, document: NormalizedDocument) -> RetrievalIndex:
        return build_index(document, embedding=self._embedding)

    def answer_question(
        self,
        index: RetrievalIndex,
        question: str,
    ) -> QuestionTrace:
        candidates = index.search(question, top_k=5)

        async def qa_llm(prompt: dict[str, str]) -> dict[str, Any]:
            if self._call_llm is None:
                return {}
            response = await self._call_llm(
                [
                    {
                        "role": "system",
                        "content": (
                            "Chỉ trả lời bằng dữ liệu trong context. Trả JSON gồm answer và "
                            "citation_ids; không đủ nguồn thì để citation_ids rỗng."
                        ),
                    },
                    {"role": "user", "content": str(prompt)},
                ],
                _QAOutput,
            )
            return response.model_dump()

        result = asyncio.run(
            GroundedQAService(
                index,
                llm=qa_llm if self._call_llm is not None else None,
            ).answer(question, top_k=5)
        )
        by_id = {candidate.chunk_id: candidate for candidate in candidates}
        traced = [by_id[item_id] for item_id in result.retrieved_ids if item_id in by_id]
        response = QuestionResponse(
            answer=result.answer,
            insufficient_evidence=result.insufficient_evidence,
            citation_ids=result.citation_ids,
            latency_ms=result.latency_ms,
        )
        return QuestionTrace(
            response=response,
            retrieved_ids=tuple(item.chunk_id for item in traced),
            retrieval_context=tuple(item.chunk.text for item in traced),
            retrieval_scores=tuple(float(item.score) for item in traced),
        )

    def to_page_blocks(self, processed_document: ProcessedDocument) -> list[PageBlock]:
        return [
            PageBlock(kind="text", text=page.content, page_number=page.page_number)
            for page in processed_document.stitched_pages
        ]

    def _load_document(self, *, file_name: str, file_bytes: bytes) -> ProcessedDocument:
        suffix = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if suffix == ".pdf":
            return self._load_pdf_document(file_name=file_name, file_bytes=file_bytes)
        if suffix == ".docx":
            return self._load_docx_document(file_name=file_name, file_bytes=file_bytes)
        raise ValueError(f"Unsupported file type: {suffix or file_name}")

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

    def _normalize_document(
        self,
        *,
        document_id: str,
        file_name: str,
        processed_document: ProcessedDocument,
    ) -> NormalizedDocument:
        chunks: list[DocumentChunk] = []
        citations: dict[str, DomainCitation] = {}
        for page in processed_document.stitched_pages:
            paragraphs = [
                paragraph.strip()
                for paragraph in re.split(r"\n{2,}", page.content)
                if paragraph.strip()
            ]
            if not paragraphs and page.content.strip():
                paragraphs = [page.content.strip()]
            for paragraph_number, paragraph in enumerate(paragraphs, start=1):
                chunk_id = f"P{page.page_number}-D{paragraph_number}"
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    page=page.page_number,
                    text=paragraph,
                )
                chunks.append(chunk)
                citations[chunk_id] = DomainCitation(
                    page=page.page_number,
                    excerpt=self._shorten(paragraph, 240),
                )
        return NormalizedDocument(
            document_id=document_id,
            file_name=file_name,
            page_count=processed_document.page_count,
            chunks=chunks,
            citations=citations,
        )

    def _build_report(
        self,
        *,
        document_id: str,
        processed_document: ProcessedDocument,
        normalized_document: NormalizedDocument,
        file_name: str,
    ) -> DocumentReport:
        if self._call_llm is not None and normalized_document.chunks:
            try:
                intelligence = asyncio.run(
                    build_intelligence(
                        normalized_document,
                        call_llm=self._call_llm,
                    )
                )
                return self._build_llm_report(
                    document_id=document_id,
                    file_name=file_name,
                    normalized_document=normalized_document,
                    intelligence=intelligence,
                )
            except Exception:
                # Availability-first fallback is explicit in the response and is
                # rejected by release evaluation, so it cannot silently pass.
                pass
        return self._build_legacy_report(
            document_id=document_id,
            processed_document=processed_document,
            file_name=file_name,
        )

    def _build_llm_report(
        self,
        *,
        document_id: str,
        file_name: str,
        normalized_document: NormalizedDocument,
        intelligence: IntelligenceReport,
    ) -> DocumentReport:
        citations = {
            item_id: Citation(**citation.model_dump())
            for item_id, citation in normalized_document.citations.items()
        }

        def summary_items(items: list[Any]) -> list[SummaryItem]:
            return [
                SummaryItem(text=item.text, citation_ids=list(item.citation_ids))
                for item in items
            ]

        return DocumentReport(
            document_id=document_id,
            file_name=file_name,
            page_count=normalized_document.page_count,
            processing_seconds=0.0,
            summary=DocumentSummary(
                context=summary_items(intelligence.summary.context),
                main_content=summary_items(intelligence.summary.main_content),
                decision_points=summary_items(intelligence.summary.decision_points),
                impact=summary_items(intelligence.summary.impact),
            ),
            terms=[
                TermItem(
                    term=term.term,
                    explanation=term.explanation,
                    citation_ids=list(term.citation_ids),
                )
                for term in intelligence.terms
            ],
            suggested_questions=[
                SuggestedQuestion(
                    question=question.question,
                    rationale=question.rationale,
                    citation_ids=list(question.citation_ids),
                )
                for question in intelligence.suggested_questions
            ],
            related_documents=self._build_related_documents(citations),
            citations=citations,
            generation_mode="llm",
            quality=intelligence.quality.model_dump(mode="json"),
        )

    def _build_legacy_report(
        self,
        *,
        document_id: str,
        processed_document: ProcessedDocument,
        file_name: str,
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

        return DocumentReport(
            document_id=document_id,
            file_name=file_name,
            page_count=processed_document.page_count,
            processing_seconds=processed_document.processing_seconds,
            summary=summary,
            terms=terms,
            suggested_questions=suggested_questions,
            related_documents=self._build_related_documents(citation_map),
            citations=citation_map,
            generation_mode="heuristic_fallback",
            quality=None,
        )

    def _build_related_documents(self, citation_map: dict[str, Citation]) -> list[RelatedDocument]:
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

    def _question_citations_to_ids(self, citations: list[str], page_count: int) -> list[str]:
        pages = self._pages_from_labels(citations)
        if not pages:
            pages = [1]
        pages = [page for page in pages if 1 <= page <= page_count]
        if not pages:
            pages = [1]
        return [self._citation_id_for_page(page) for page in pages]

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
