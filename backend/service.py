"""In-memory backend runtime for document upload and orchestration."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import threading
import time
from pathlib import Path

from .errors import ApiError
from .orchestrator import DocumentOrchestrator, ProcessedDocument
from .schemas import (
    DocumentReport,
    DocumentStatus,
    PageBlock,
    PageResponse,
    QuestionResponse,
    StatusResponse,
    UploadResponse,
)


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
PROCESSING_WAIT_TIMEOUT_SECONDS = 15.0


@dataclass
class PageRecord:
    page_number: int
    text: str
    blocks: list[PageBlock] = field(default_factory=list)


@dataclass
class DocumentRecord:
    document_id: str
    file_name: str
    file_size_bytes: int
    file_bytes: bytes
    status: DocumentStatus = "queued"
    stage: str = "queued"
    progress: int = 0
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime | None = None
    processing_seconds: float = 0.0
    cached: bool = False
    page_count: int = 0
    pages: list[PageRecord] = field(default_factory=list)
    report: DocumentReport | None = None
    processed_document: ProcessedDocument | None = field(default=None, repr=False, compare=False)
    future: Future[None] | None = field(default=None, repr=False, compare=False)


class DocumentStore:
    """Thread-safe store and scheduler for uploaded documents."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._documents: dict[str, DocumentRecord] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="antipaper-job")
        self._orchestrator = DocumentOrchestrator()

    def submit_upload(self, file_name: str, file_bytes: bytes) -> tuple[DocumentRecord, bool]:
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise ApiError(
                code="FILE_TOO_LARGE",
                message="File too large. Maximum size is 25 MB.",
                status_code=413,
                retryable=False,
            )

        extension = Path(file_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise ApiError(
                code="UNSUPPORTED_FILE",
                message="Only PDF or DOCX files are supported.",
                status_code=415,
                retryable=False,
            )

        document_id = hashlib.sha256(file_bytes).hexdigest()
        with self._lock:
            existing = self._documents.get(document_id)
            if existing is not None:
                existing.cached = existing.status == "completed"
                existing.updated_at = datetime.now(timezone.utc)
                return existing, True

            record = DocumentRecord(
                document_id=document_id,
                file_name=file_name,
                file_size_bytes=len(file_bytes),
                file_bytes=file_bytes,
            )
            self._documents[document_id] = record
            self._start_processing(record)
            return record, False

    def ensure_processed(self, document_id: str) -> DocumentRecord:
        record = self.get(document_id)
        if record.status in {"queued", "processing"}:
            self._wait_for_completion(record)
        return self.get(document_id)

    def get(self, document_id: str) -> DocumentRecord:
        with self._lock:
            try:
                return self._documents[document_id]
            except KeyError as exc:
                raise ApiError(
                    code="DOCUMENT_NOT_FOUND",
                    message="Document not found.",
                    status_code=404,
                    retryable=False,
                ) from exc

    def process_document(self, document_id: str) -> None:
        record = self.get(document_id)
        if record.status == "completed":
            return

        start = time.perf_counter()
        try:
            self._mark_processing(record, "parsing", 15)
            result = self._orchestrator.process(
                document_id=record.document_id,
                file_name=record.file_name,
                file_bytes=record.file_bytes,
            )
            processing_seconds = round(time.perf_counter() - start, 3)
            record.processed_document = result.processed_document
            record.processed_document.processing_seconds = processing_seconds
            record.pages = self._build_pages(result.processed_document)
            record.page_count = result.processed_document.page_count
            record.report = result.report.model_copy(update={"processing_seconds": processing_seconds})
            record.status = "completed"
            record.stage = "ready"
            record.progress = 100
            record.error = None
            record.processing_seconds = processing_seconds
            record.processed_at = datetime.now(timezone.utc)
            record.updated_at = datetime.now(timezone.utc)
        except ApiError:
            self._mark_failed(record, "PROCESSING_FAILED", "Document processing failed.")
            raise
        except Exception as exc:  # pragma: no cover - defensive fallback
            self._mark_failed(record, "PROCESSING_FAILED", str(exc))
        finally:
            record.future = None

    def get_status(self, document_id: str) -> StatusResponse:
        record = self.get(document_id)
        elapsed = (datetime.now(timezone.utc) - record.created_at).total_seconds()
        return StatusResponse(
            document_id=record.document_id,
            status=record.status,
            stage=record.stage,
            progress=record.progress,
            elapsed_seconds=round(max(elapsed, 0.0), 3),
            error=record.error,
        )

    def get_report(self, document_id: str) -> DocumentReport:
        record = self.ensure_processed(document_id)
        if record.report is None:
            raise ApiError(
                code="PROCESSING_FAILED",
                message="Report is not ready yet.",
                status_code=409,
                retryable=True,
            )
        return record.report

    def get_page(self, document_id: str, page_number: int) -> PageResponse:
        record = self.ensure_processed(document_id)
        if record.processed_document is None:
            raise ApiError(
                code="PROCESSING_FAILED",
                message="Document pages are not ready yet.",
                status_code=409,
                retryable=True,
            )
        if page_number < 1 or page_number > len(record.pages):
            raise ApiError(
                code="DOCUMENT_NOT_FOUND",
                message="Requested page not found.",
                status_code=404,
                retryable=False,
            )
        page = record.pages[page_number - 1]
        return PageResponse(
            document_id=record.document_id,
            page_number=page.page_number,
            text=page.text,
            blocks=page.blocks,
        )

    def answer_question(self, document_id: str, question: str) -> QuestionResponse:
        record = self.ensure_processed(document_id)
        if record.processed_document is None:
            raise ApiError(
                code="PROCESSING_FAILED",
                message="Document is not ready for question answering.",
                status_code=409,
                retryable=True,
            )
        return self._orchestrator.answer_question(record.processed_document, question)

    def _start_processing(self, record: DocumentRecord) -> None:
        record.status = "queued"
        record.stage = "queued"
        record.progress = 0
        record.error = None
        record.updated_at = datetime.now(timezone.utc)
        record.future = self._executor.submit(self.process_document, record.document_id)

    def _wait_for_completion(
        self,
        record: DocumentRecord,
        timeout: float = PROCESSING_WAIT_TIMEOUT_SECONDS,
    ) -> None:
        future = record.future
        if future is None:
            self.process_document(record.document_id)
            return

        try:
            future.result(timeout=timeout)
        except FutureTimeoutError as exc:
            raise ApiError(
                code="MODEL_TIMEOUT",
                message="Document processing timed out.",
                status_code=504,
                retryable=True,
            ) from exc

    def _mark_processing(self, record: DocumentRecord, stage: str, progress: int) -> None:
        record.status = "processing"
        record.stage = stage
        record.progress = progress
        record.error = None
        record.updated_at = datetime.now(timezone.utc)

    def _mark_failed(self, record: DocumentRecord, code: str, message: str) -> None:
        record.status = "failed"
        record.stage = "failed"
        record.progress = 100
        record.error = f"{code}: {message}"
        record.updated_at = datetime.now(timezone.utc)

    def _build_pages(self, processed_document: ProcessedDocument) -> list[PageRecord]:
        pages: list[PageRecord] = []
        for page in processed_document.stitched_pages:
            text = page.content.strip()
            pages.append(
                PageRecord(
                    page_number=page.page_number,
                    text=text,
                    blocks=[PageBlock(kind="text", text=text, page_number=page.page_number)],
                )
            )
        return pages


class AntipaperService:
    """Facade used by the FastAPI routes."""

    def __init__(self) -> None:
        self.store = DocumentStore()

    def submit_document(self, file_name: str, file_bytes: bytes) -> UploadResponse:
        record, cached = self.store.submit_upload(file_name, file_bytes)
        return UploadResponse(
            document_id=record.document_id,
            status=record.status,
            cached=cached,
        )

    def process_document(self, document_id: str) -> None:
        self.store.process_document(document_id)

    def get_status(self, document_id: str) -> StatusResponse:
        return self.store.get_status(document_id)

    def get_report(self, document_id: str) -> DocumentReport:
        return self.store.get_report(document_id)

    def get_page(self, document_id: str, page_number: int) -> PageResponse:
        return self.store.get_page(document_id, page_number)

    def answer_question(self, document_id: str, question: str) -> QuestionResponse:
        return self.store.answer_question(document_id, question)
