"""Adapters from Antipaper domain objects to evaluation-ready traces."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import hashlib
from pathlib import Path

from src.intelligence import NormalizedDocument
from src.services.orchestrator import DocumentOrchestrator, OrchestrationResult, ProcessedDocument, QuestionTrace
from src.retrieval import RetrievalIndex


@dataclass
class BenchmarkApplication:
    path: Path
    file_bytes: bytes
    document_id: str
    orchestrator: DocumentOrchestrator
    document: NormalizedDocument
    index: RetrievalIndex
    processed_document: ProcessedDocument

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        use_configured_llm: bool,
    ) -> "BenchmarkApplication":
        source = Path(path).resolve()
        payload = source.read_bytes()
        document_id = hashlib.sha256(payload).hexdigest()
        orchestrator = DocumentOrchestrator(use_configured_llm=use_configured_llm)
        document, pages = orchestrator.ingest(
            document_id=document_id,
            file_name=source.name,
            file_bytes=payload,
        )
        processed_document = ProcessedDocument(
            source_name=source.name,
            page_count=document.page_count,
            stitched_pages=pages,
            normalized_document=document,
            chunks=list(document.chunks),
        )
        return cls(
            path=source,
            file_bytes=payload,
            document_id=document_id,
            orchestrator=orchestrator,
            document=document,
            index=orchestrator.build_retrieval_index(document),
            processed_document=processed_document,
        )

    def answer(self, question: str) -> QuestionTrace:
        return asyncio.run(self.orchestrator.answer_question_async(self.processed_document, question, self.index))

    def generate_report(self) -> OrchestrationResult:
        return self.orchestrator.process(
            document_id=self.document_id,
            file_name=self.path.name,
            file_bytes=self.file_bytes,
        )
