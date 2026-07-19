"""In-memory document lifecycle and SQLite task-audit facade."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import base64
import os
import threading
import time
from typing import Callable
from uuid import uuid4

import fitz

from ..errors import ApiError
from ..ingestion import FileTooLargeError, IngestionError, UnsupportedFileError
from ..integrations.tavily import RelatedDocumentFinder
from ..integrations.llm import LlmClientConfigurationError, LlmClientError, LlmClientTimeoutError
from ..intelligence import IntelligenceQualityError
from ..persistence.history import TaskHistoryStore
from ..retrieval import RetrievalIndex, build_index
from ..schemas import (
    DocumentReport, DocumentStatus, ErrorDetail, PageBlock, PageResponse,
    QuestionResponse, SourcePreview, StageTiming, StatusResponse, TaskHistoryItem,
    TaskHistoryPage, UploadResponse,
)
from .orchestrator import (
    AnalysisTextLimitExceeded,
    DocumentOrchestrator,
    ProcessedDocument,
    ProcessingDeadlineExceeded,
    QuestionTrace,
)


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
WORKER_DEADLINE_SECONDS = float(os.getenv("PROCESSING_DEADLINE_SECONDS", "110"))
STAGE_QUEUED, STAGE_PARSING, STAGE_MAPPING, STAGE_REDUCING, STAGE_QUESTIONS, STAGE_READY, STAGE_FAILED = (
    "queued", "parsing", "mapping", "reducing", "generating_questions", "ready", "failed"
)


@dataclass
class PageRecord:
    page_number: int
    text: str
    blocks: list[PageBlock]


@dataclass
class DocumentRecord:
    document_id: str
    file_name: str
    file_size_bytes: int
    file_bytes: bytes
    status: DocumentStatus = "queued"
    stage: str = STAGE_QUEUED
    progress: int = 0
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime | None = None
    processing_seconds: float = 0.0
    page_count: int = 0
    pages: list[PageRecord] = field(default_factory=list)
    report: DocumentReport | None = None
    processed_document: ProcessedDocument | None = field(default=None, repr=False)
    retrieval_index: RetrievalIndex | None = field(default=None, repr=False)
    last_question_trace: QuestionTrace | None = field(default=None, repr=False)
    future: Future[None] | None = field(default=None, repr=False)


class DocumentStore:
    """Active documents only. No content, report, or index is persisted."""

    def __init__(
        self,
        *,
        transition_listener: Callable[[DocumentRecord], None] | None = None,
        related_document_finder: RelatedDocumentFinder | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._documents: dict[str, DocumentRecord] = {}
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="antipaper")
        self._orchestrator = DocumentOrchestrator()
        self._transition_listener = transition_listener
        self._related_document_finder = related_document_finder or RelatedDocumentFinder.from_env()

    @property
    def llm_enabled(self) -> bool:
        return self._orchestrator.llm_enabled

    def submit_upload(self, file_name: str, file_bytes: bytes) -> DocumentRecord:
        self._validate_upload(file_name, file_bytes)
        record = DocumentRecord(
            document_id=str(uuid4()),
            file_name=Path(file_name).name or "uploaded-file",
            file_size_bytes=len(file_bytes),
            file_bytes=file_bytes,
        )
        with self._lock:
            self._documents[record.document_id] = record
        self._start_processing(record)
        return record

    def get(self, document_id: str) -> DocumentRecord:
        with self._lock:
            record = self._documents.get(document_id)
        if record is None:
            raise ApiError(
                code="DOCUMENT_NOT_FOUND",
                message="Document is no longer active. Upload it again to open its report.",
                status_code=404,
            )
        return record

    def process_document(self, document_id: str) -> None:
        record = self.get(document_id)
        if record.status == "completed":
            return
        started = time.perf_counter()
        queued_ms = max((datetime.now(timezone.utc) - record.created_at).total_seconds() * 1000, 0.0)

        def on_stage(stage: str) -> None:
            progress = {STAGE_MAPPING: 45, STAGE_REDUCING: 65, STAGE_QUESTIONS: 80}.get(stage, 20)
            self._transition(record, status="processing", stage=stage, progress=progress)

        try:
            self._transition(record, status="processing", stage=STAGE_PARSING, progress=15)
            result = self._orchestrator.process(
                document_id=record.document_id,
                file_name=record.file_name,
                file_bytes=record.file_bytes,
                deadline_seconds=WORKER_DEADLINE_SECONDS,
                stage_callback=on_stage,
            )
            elapsed = time.perf_counter() - started
            persist_started = time.perf_counter()
            record.processed_document = result.processed_document
            record.retrieval_index = build_index(result.normalized_document)
            record.pages = [
                PageRecord(page.page_number, page.content, [PageBlock(kind="text", text=page.content, page_number=page.page_number)])
                for page in result.processed_document.stitched_pages
            ]
            record.page_count = result.processed_document.page_count
            if time.perf_counter() - started > WORKER_DEADLINE_SECONDS:
                raise ProcessingDeadlineExceeded("Processing deadline exceeded during persist.")
            elapsed = time.perf_counter() - started
            record.processing_seconds = round(elapsed, 3)
            persist_ms = round((time.perf_counter() - persist_started) * 1000, 3)
            record.report = result.report.model_copy(
                update={
                    "processing_seconds": record.processing_seconds,
                    "enrichment_status": "pending" if self._related_document_finder else "not_configured",
                    "quality": result.report.quality.model_copy(
                        update={
                            "queue_ms": round(queued_ms, 3),
                            "stage_timings": [
                                *result.report.quality.stage_timings,
                                StageTiming(stage="persist", duration_ms=persist_ms),
                            ],
                        }
                    ),
                }
            )
            record.processed_at = datetime.now(timezone.utc)
            self._transition(record, status="completed", stage=STAGE_READY, progress=100)
            if self._related_document_finder:
                self._executor.submit(self._enrich_related_documents, record.document_id)
        except UnsupportedFileError as exc:
            self._fail(record, "UNSUPPORTED_FILE", str(exc))
        except FileTooLargeError as exc:
            self._fail(record, "FILE_TOO_LARGE", str(exc))
        except ProcessingDeadlineExceeded as exc:
            self._fail(record, "GLOBAL_DEADLINE_EXCEEDED", str(exc))
        except LlmClientTimeoutError as exc:
            self._fail(record, "MODEL_TIMEOUT", str(exc))
        except LlmClientConfigurationError as exc:
            self._fail(record, "LLM_NOT_CONFIGURED", str(exc))
        except IntelligenceQualityError as exc:
            self._fail(record, "LLM_GENERATION_FAILED", str(exc))
        except LlmClientError as exc:
            self._fail(record, "LLM_GENERATION_FAILED", str(exc))
        except AnalysisTextLimitExceeded as exc:
            self._fail(record, "ANALYSIS_TEXT_LIMIT_EXCEEDED", str(exc))
        except IngestionError as exc:
            self._fail(record, "PROCESSING_FAILED", str(exc))
        except Exception as exc:  # Defensive boundary for background workers.
            self._fail(record, "PROCESSING_FAILED", str(exc))
        finally:
            record.future = None

    def get_status(self, document_id: str) -> StatusResponse:
        record = self.get(document_id)
        elapsed = (datetime.now(timezone.utc) - record.created_at).total_seconds()
        error = None if not record.error else ErrorDetail(
            code=record.error.split(":", 1)[0],
            message=record.error.split(":", 1)[-1].strip(),
        )
        return StatusResponse(document_id=record.document_id, status=record.status, stage=record.stage,
                              progress=record.progress, elapsed_seconds=round(max(elapsed, 0), 3), error=error)

    def get_report(self, document_id: str) -> DocumentReport:
        record = self._wait_for_completion(self.get(document_id))
        if record.report is not None:
            return record.report
        self._raise_processing_error(record)

    def get_page(self, document_id: str, page_number: int) -> PageResponse:
        record = self._wait_for_completion(self.get(document_id))
        if page_number < 1 or page_number > len(record.pages):
            raise ApiError(code="DOCUMENT_NOT_FOUND", message="Requested page not found.", status_code=404)
        page = record.pages[page_number - 1]
        return PageResponse(document_id=document_id, page_number=page_number, text=page.text,
                            blocks=page.blocks, source_preview=self._render_preview(record, page_number))

    async def answer_question(self, document_id: str, question: str) -> QuestionResponse:
        record = await asyncio.to_thread(self._wait_for_completion, self.get(document_id))
        if record.processed_document is None:
            self._raise_processing_error(record)
        trace = await self._orchestrator.answer_question_async(
            record.processed_document, question, record.retrieval_index,
        )
        record.last_question_trace = trace
        return trace.response

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _validate_upload(self, file_name: str, file_bytes: bytes) -> None:
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise ApiError(code="FILE_TOO_LARGE", message="File too large. Maximum size is 25 MB.", status_code=413)
        if Path(file_name).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ApiError(code="UNSUPPORTED_FILE", message="Only PDF or DOCX files are supported.", status_code=415)

    def _start_processing(self, record: DocumentRecord) -> None:
        self._notify(record)
        record.future = self._executor.submit(self.process_document, record.document_id)

    def _wait_for_completion(self, record: DocumentRecord) -> DocumentRecord:
        if record.status in {"queued", "processing"}:
            raise ApiError(
                code="DOCUMENT_PROCESSING",
                message="Document processing is still in progress.",
                status_code=409,
                retryable=True,
            )
        return record

    def _transition(self, record: DocumentRecord, *, status: DocumentStatus, stage: str, progress: int) -> None:
        with self._lock:
            record.status, record.stage, record.progress = status, stage, progress
            record.updated_at = datetime.now(timezone.utc)
        self._notify(record)

    def _fail(self, record: DocumentRecord, code: str, message: str) -> None:
        record.error = f"{code}: {message}"
        record.processing_seconds = round(time.perf_counter() - record.created_at.timestamp(), 3) if False else record.processing_seconds
        self._transition(record, status="failed", stage=STAGE_FAILED, progress=100)

    def _notify(self, record: DocumentRecord) -> None:
        if self._transition_listener:
            self._transition_listener(record)

    @staticmethod
    def _raise_processing_error(record: DocumentRecord) -> None:
        if record.error:
            code, _, message = record.error.partition(": ")
            raise ApiError(code=code, message=message or "Document processing failed.", status_code=409)
        raise ApiError(code="PROCESSING_FAILED", message="Report is not ready yet.", status_code=409, retryable=True)

    @staticmethod
    def _render_preview(record: DocumentRecord, page_number: int) -> SourcePreview | None:
        if Path(record.file_name).suffix.lower() != ".pdf":
            return None
        try:
            with fitz.open(stream=record.file_bytes, filetype="pdf") as document:
                page = document[page_number - 1]
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
                encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
                return SourcePreview(mime_type="image/png", data_url=f"data:image/png;base64,{encoded}",
                                     width=pixmap.width, height=pixmap.height, page_number=page_number)
        except Exception:
            return None

    def _enrich_related_documents(self, document_id: str) -> None:
        record = self.get(document_id)
        try:
            if record.processed_document is None or record.report is None or self._related_document_finder is None:
                return
            related = self._related_document_finder.find(record.processed_document.normalized_document)[:5]
            with self._lock:
                if record.report:
                    record.report = record.report.model_copy(update={"related_documents": related, "enrichment_status": "completed"})
        except Exception:
            with self._lock:
                if record.report:
                    record.report = record.report.model_copy(update={"enrichment_status": "failed"})


class AntipaperService:
    """FastAPI facade; history is durable, documents are intentionally not."""

    def __init__(self, *, history_path: Path | None = None, **_: object) -> None:
        database = history_path or Path(os.getenv("HISTORY_DB_PATH", ".runtime/history.sqlite3"))
        self.history = TaskHistoryStore(database)
        self.store = DocumentStore(transition_listener=self._record_document_transition)

    @property
    def llm_status(self) -> str:
        return "enabled" if self.store.llm_enabled else "disabled"

    def submit_document(self, file_name: str, file_bytes: bytes, user_id: str = "demo-user") -> UploadResponse:
        task = self.history.create_task(user_id=user_id, task_type="document_processing", display_name=file_name)
        try:
            record = self.store.submit_upload(file_name, file_bytes)
            self.history.attach_document(task.task_id, document_id=record.document_id)
            self._record_document_transition(record)
            return UploadResponse(document_id=record.document_id, status=record.status, task_id=task.task_id)
        except ApiError as exc:
            self.history.update_task(task.task_id, status="failed", stage=STAGE_FAILED, progress=100,
                                     error_code=exc.code, error_message=exc.message)
            raise

    def process_document(self, document_id: str) -> None: self.store.process_document(document_id)
    def get_status(self, document_id: str) -> StatusResponse: return self.store.get_status(document_id)
    def get_report(self, document_id: str) -> DocumentReport: return self.store.get_report(document_id)
    def get_page(self, document_id: str, page_number: int) -> PageResponse: return self.store.get_page(document_id, page_number)

    async def answer_question(self, document_id: str, question: str, user_id: str = "demo-user") -> QuestionResponse:
        task = self.history.create_task(user_id=user_id, task_type="question_answer", display_name=question[:160],
                                        document_id=document_id, status="processing", stage="answering", progress=50)
        try:
            response = await self.store.answer_question(document_id, question)
        except ApiError as exc:
            self.history.update_task(task.task_id, status="failed", stage=STAGE_FAILED, progress=100,
                                     error_code=exc.code, error_message=exc.message)
            raise
        self.history.update_task(task.task_id, status="completed", stage=STAGE_READY, progress=100,
                                 duration_seconds=response.latency_ms / 1000)
        return response.model_copy(update={"task_id": task.task_id})

    def list_history(self, **kwargs: object) -> TaskHistoryPage: return self.history.list_tasks(**kwargs)
    def get_history(self, *, user_id: str, task_id: str) -> TaskHistoryItem: return self.history.get_task(user_id=user_id, task_id=task_id)
    def delete_history(self, *, user_id: str, task_id: str) -> None: self.history.delete_task(user_id=user_id, task_id=task_id)
    def delete_history_session(self, *, user_id: str, document_id: str) -> None:
        self.history.delete_session(user_id=user_id, document_id=document_id)

    def _record_document_transition(self, record: DocumentRecord) -> None:
        code = message = None
        if record.error:
            code, _, message = record.error.partition(": ")
        self.history.update_open_document_tasks(document_id=record.document_id, status=record.status,
                                                stage=record.stage, progress=record.progress,
                                                error_code=code, error_message=message,
                                                duration_seconds=record.processing_seconds or None)

    def shutdown(self) -> None: self.store.shutdown()
