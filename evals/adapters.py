"""Adapters from Antipaper domain objects to evaluation-ready traces."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from backend.intelligence import NormalizedDocument
from backend.orchestrator import DocumentOrchestrator, OrchestrationResult, QuestionTrace
from backend.retrieval import RetrievalIndex


@dataclass
class BenchmarkApplication:
    path: Path
    file_bytes: bytes
    document_id: str
    orchestrator: DocumentOrchestrator
    document: NormalizedDocument
    index: RetrievalIndex

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
        _, document = orchestrator.ingest(
            document_id=document_id,
            file_name=source.name,
            file_bytes=payload,
        )
        return cls(
            path=source,
            file_bytes=payload,
            document_id=document_id,
            orchestrator=orchestrator,
            document=document,
            index=orchestrator.build_retrieval_index(document),
        )

    def answer(self, question: str) -> QuestionTrace:
        return self.orchestrator.answer_question(self.index, question)

    def generate_report(self) -> OrchestrationResult:
        return self.orchestrator.process(
            document_id=self.document_id,
            file_name=self.path.name,
            file_bytes=self.file_bytes,
        )
