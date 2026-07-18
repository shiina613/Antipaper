"""In-memory backend runtime for document upload and orchestration."""

from __future__ import annotations

import base64
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import hashlib
import os
import threading
import time
from pathlib import Path
from typing import Callable

import fitz

from .intelligence import NormalizedDocument
from .retrieval import RetrievalIndex

from .errors import ApiError
from .history import TaskHistoryStore
from .orchestrator import (
    DocumentOrchestrator,
    ProcessedDocument,
    QuestionTrace,
    StitchedPage,
)
from .schemas import (
    DocumentReport,
    DocumentStatus,
    ErrorDetail,
    PageBlock,
    PageResponse,
    QuestionResponse,
    SourcePreview,
    StatusResponse,
    TaskHistoryItem,
    TaskHistoryPage,
    TaskType,
    UploadResponse,
)


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
PROCESSING_WAIT_TIMEOUT_SECONDS = 15.0
# Questions now retain their complete, question-specific evidence provenance.
# Bumping the schema prevents cached reports with the earlier single-paragraph
# summaries from rehydrating after a backend restart.
ARTIFACT_SCHEMA_VERSION = 9
STAGE_QUEUED = "queued"
STAGE_PARSING = "parsing"
STAGE_GENERATING = "generating"
STAGE_READY = "ready"
STAGE_FAILED = "failed"
FAILED_ERROR_STATUSES = {
    "FILE_TOO_LARGE": 413,
    "UNSUPPORTED_FILE": 415,
    "INVALID_OUTPUT": 502,
    "MODEL_TIMEOUT": 504,
    "PROCESSING_FAILED": 409,
}


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
    normalized_document: NormalizedDocument | None = field(default=None, repr=False, compare=False)
    retrieval_index: RetrievalIndex | None = field(default=None, repr=False, compare=False)
    last_question_trace: QuestionTrace | None = field(default=None, repr=False, compare=False)
    future: Future[None] | None = field(default=None, repr=False, compare=False)


class DocumentStore:
    """Thread-safe store and scheduler for uploaded documents."""

    def __init__(
        self,
        artifact_root: Path | None = None,
        transition_listener: Callable[[DocumentRecord], None] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._documents: dict[str, DocumentRecord] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="antipaper-job")
        self._orchestrator = DocumentOrchestrator()
        self._transition_listener = transition_listener
        root = artifact_root or Path(os.getenv("ARTIFACT_DIR", ".artifacts"))
        self._artifact_root = (root.expanduser() / "documents").resolve()
        self._artifact_root.mkdir(parents=True, exist_ok=True)

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

            rehydrated = self._rehydrate_from_artifacts(document_id)
            if rehydrated is not None:
                rehydrated.cached = True
                rehydrated.updated_at = datetime.now(timezone.utc)
                self._documents[document_id] = rehydrated
                return rehydrated, True

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
        try:
            if record.status in {"queued", "processing"}:
                self._wait_for_completion(record)
        finally:
            # Reconcile persistent task history after observing the worker.
            # This must also run when the record became terminal immediately
            # before the status check: its earlier callback may have happened
            # before submit_document attached the task to the document.
            self._notify_transition(record)
        return self.get(document_id)

    def get(self, document_id: str) -> DocumentRecord:
        with self._lock:
            record = self._documents.get(document_id)
            if record is not None:
                return record

            rehydrated = self._rehydrate_from_artifacts(document_id)
            if rehydrated is not None:
                self._documents[document_id] = rehydrated
                return rehydrated

            raise ApiError(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found.",
                status_code=404,
                retryable=False,
            )

    def process_document(self, document_id: str) -> None:
        record = self.get(document_id)
        if record.status == "completed":
            return

        start = time.perf_counter()
        try:
            self._mark_processing(record, STAGE_PARSING, 20)
            self._mark_processing(record, STAGE_GENERATING, 60)
            result = self._orchestrator.process(
                document_id=record.document_id,
                file_name=record.file_name,
                file_bytes=record.file_bytes,
            )
            self._validate_orchestration_result(record, result)
            processing_seconds = round(time.perf_counter() - start, 3)
            record.processed_document = result.processed_document
            record.processed_document.processing_seconds = processing_seconds
            record.normalized_document = result.normalized_document
            record.retrieval_index = self._orchestrator.build_retrieval_index(
                result.normalized_document
            )
            record.pages = self._build_pages(result.processed_document)
            record.page_count = result.processed_document.page_count
            record.report = result.report.model_copy(update={"processing_seconds": processing_seconds})
            record.status = "completed"
            record.stage = STAGE_READY
            record.progress = 100
            record.error = None
            record.processing_seconds = processing_seconds
            record.processed_at = datetime.now(timezone.utc)
            record.updated_at = datetime.now(timezone.utc)
            self._persist_artifacts(record)
            self._notify_transition(record)
        except ApiError as exc:
            self._mark_failed(record, exc.code, exc.message)
            raise
        except ValueError as exc:
            self._mark_failed(record, "INVALID_OUTPUT", str(exc))
            raise ApiError(
                code="INVALID_OUTPUT",
                message="Document processing returned invalid output.",
                status_code=502,
                retryable=True,
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive fallback
            self._mark_failed(record, "PROCESSING_FAILED", str(exc))
        finally:
            record.future = None

    def get_status(self, document_id: str) -> StatusResponse:
        record = self.get(document_id)
        elapsed = (datetime.now(timezone.utc) - record.created_at).total_seconds()
        error = None
        if record.error:
            api_error = self._api_error_from_record_error(record.error)
            error = ErrorDetail(
                code=api_error.code,
                message=api_error.message,
                retryable=api_error.retryable,
            )
        return StatusResponse(
            document_id=record.document_id,
            status=record.status,
            stage=record.stage,
            progress=record.progress,
            elapsed_seconds=round(max(elapsed, 0.0), 3),
            error=error,
        )

    def get_report(self, document_id: str) -> DocumentReport:
        record = self.ensure_processed(document_id)
        if record.report is None:
            if record.status == "failed" and record.error:
                raise self._api_error_from_record_error(record.error)
            raise ApiError(
                code="PROCESSING_FAILED",
                message="Report is not ready yet.",
                status_code=409,
                retryable=True,
            )
        return record.report

    def get_page(self, document_id: str, page_number: int) -> PageResponse:
        record = self.ensure_processed(document_id)
        if record.normalized_document is None:
            if record.status == "failed" and record.error:
                raise self._api_error_from_record_error(record.error)
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
            source_preview=self._render_source_preview(record, page_number),
        )

    def answer_question(self, document_id: str, question: str) -> QuestionResponse:
        record = self.ensure_processed(document_id)
        if record.normalized_document is None:
            if record.status == "failed" and record.error:
                raise self._api_error_from_record_error(record.error)
            raise ApiError(
                code="PROCESSING_FAILED",
                message="Document is not ready for question answering.",
                status_code=409,
                retryable=True,
            )
        start = time.perf_counter()
        if record.retrieval_index is None:
            record.retrieval_index = self._orchestrator.build_retrieval_index(
                record.normalized_document
            )
        trace = self._orchestrator.answer_question(record.retrieval_index, question)
        record.last_question_trace = trace
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return trace.response.model_copy(update={"latency_ms": latency_ms})

    def _start_processing(self, record: DocumentRecord) -> None:
        record.status = "queued"
        record.stage = STAGE_QUEUED
        record.progress = 0
        record.error = None
        record.updated_at = datetime.now(timezone.utc)
        record.future = self._executor.submit(self.process_document, record.document_id)
        self._notify_transition(record)

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
        self._notify_transition(record)

    def _mark_failed(self, record: DocumentRecord, code: str, message: str) -> None:
        record.status = "failed"
        record.stage = STAGE_FAILED
        record.progress = 100
        record.error = f"{code}: {message}"
        record.updated_at = datetime.now(timezone.utc)
        self._persist_artifacts(record)
        self._notify_transition(record)

    def _notify_transition(self, record: DocumentRecord) -> None:
        if self._transition_listener is None:
            return
        try:
            self._transition_listener(record)
        except Exception:  # pragma: no cover - history must not break processing
            return

    def _validate_orchestration_result(
        self,
        record: DocumentRecord,
        result: object,
    ) -> None:
        if (
            not hasattr(result, "processed_document")
            or not hasattr(result, "normalized_document")
            or not hasattr(result, "report")
        ):
            raise ValueError("Orchestrator returned an invalid result object.")

        processed_document = getattr(result, "processed_document")
        normalized_document = getattr(result, "normalized_document")
        report = getattr(result, "report")
        if processed_document is None or normalized_document is None or report is None:
            raise ValueError("Orchestrator returned empty processing output.")

        if getattr(report, "document_id", None) != record.document_id:
            raise ValueError("Report document_id does not match the uploaded document.")
        if getattr(report, "page_count", None) != getattr(processed_document, "page_count", None):
            raise ValueError("Report page_count does not match the processed document.")
        if getattr(normalized_document, "document_id", None) != record.document_id:
            raise ValueError("Normalized document_id does not match the uploaded document.")

    def _api_error_from_record_error(self, error_text: str) -> ApiError:
        code, _, message = error_text.partition(": ")
        code = code or "PROCESSING_FAILED"
        message = message or "Document processing failed."
        return ApiError(
            code=code,
            message=message,
            status_code=FAILED_ERROR_STATUSES.get(code, 409),
            retryable=code in {"INVALID_OUTPUT", "MODEL_TIMEOUT", "PROCESSING_FAILED"},
        )

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

    def _artifact_dir(self, document_id: str) -> Path:
        return self._artifact_root / document_id

    def _manifest_path(self, document_id: str) -> Path:
        return self._artifact_dir(document_id) / "manifest.json"

    def _pages_path(self, document_id: str) -> Path:
        return self._artifact_dir(document_id) / "pages.json"

    def _report_path(self, document_id: str) -> Path:
        return self._artifact_dir(document_id) / "report.json"

    def _normalized_path(self, document_id: str) -> Path:
        return self._artifact_dir(document_id) / "normalized.json"

    def _source_path(self, document_id: str) -> Path:
        return self._artifact_dir(document_id) / "source.bin"

    def _render_source_preview(
        self,
        record: DocumentRecord,
        page_number: int,
    ) -> SourcePreview | None:
        if Path(record.file_name).suffix.lower() != ".pdf" or not record.file_bytes:
            return None
        try:
            with fitz.open(stream=record.file_bytes, filetype="pdf") as document:
                if page_number < 1 or page_number > document.page_count:
                    return None
                page = document[page_number - 1]
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
                encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
                return SourcePreview(
                    mime_type="image/png",
                    data_url=f"data:image/png;base64,{encoded}",
                    width=pixmap.width,
                    height=pixmap.height,
                    page_number=page_number,
                )
        except Exception:
            return None

    def _persist_artifacts(self, record: DocumentRecord) -> None:
        try:
            artifact_dir = self._artifact_dir(record.document_id)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            if record.file_bytes:
                self._source_path(record.document_id).write_bytes(record.file_bytes)
            self._manifest_path(record.document_id).write_text(
                json.dumps(self._serialize_manifest(record), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if (
                record.status == "completed"
                and record.report is not None
                and record.normalized_document is not None
            ):
                self._pages_path(record.document_id).write_text(
                    json.dumps(self._serialize_pages(record.pages), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self._report_path(record.document_id).write_text(
                    record.report.model_dump_json(indent=2),
                    encoding="utf-8",
                )
                self._normalized_path(record.document_id).write_text(
                    record.normalized_document.model_dump_json(indent=2),
                    encoding="utf-8",
                )
        except Exception:  # pragma: no cover - artifact persistence is best effort
            return

    def _rehydrate_from_artifacts(self, document_id: str) -> DocumentRecord | None:
        manifest_path = self._manifest_path(document_id)
        report_path = self._report_path(document_id)
        pages_path = self._pages_path(document_id)
        normalized_path = self._normalized_path(document_id)
        source_path = self._source_path(document_id)
        if not manifest_path.exists():
            return None

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if int(manifest.get("artifact_schema_version", 0)) != ARTIFACT_SCHEMA_VERSION:
                return None
            record = DocumentRecord(
                document_id=document_id,
                file_name=str(manifest["file_name"]),
                file_size_bytes=int(manifest["file_size_bytes"]),
                file_bytes=source_path.read_bytes() if source_path.exists() else b"",
                status=str(manifest["status"]),
                stage=str(manifest["stage"]),
                progress=int(manifest["progress"]),
                error=manifest.get("error"),
                created_at=datetime.fromisoformat(str(manifest["created_at"])),
                updated_at=datetime.fromisoformat(str(manifest["updated_at"])),
                processed_at=self._parse_datetime(manifest.get("processed_at")),
                processing_seconds=float(manifest.get("processing_seconds", 0.0)),
                cached=bool(manifest.get("cached", False)),
                page_count=int(manifest.get("page_count", 0)),
            )
            if record.status == "completed":
                if (
                    not report_path.exists()
                    or not pages_path.exists()
                    or not normalized_path.exists()
                ):
                    return None
                record.report = DocumentReport.model_validate_json(report_path.read_text(encoding="utf-8"))
                record.pages = self._deserialize_pages(json.loads(pages_path.read_text(encoding="utf-8")))
                record.normalized_document = NormalizedDocument.model_validate_json(
                    normalized_path.read_text(encoding="utf-8")
                )
                record.retrieval_index = self._orchestrator.build_retrieval_index(
                    record.normalized_document
                )
                record.processed_document = ProcessedDocument(
                    source_name=record.file_name,
                    page_count=record.page_count,
                    stitched_pages=[
                        StitchedPage(page_number=page.page_number, content=page.text)
                        for page in record.pages
                    ],
                )
            return record
        except Exception:  # pragma: no cover - corrupted artifacts are treated as cache miss
            return None

    def _serialize_manifest(self, record: DocumentRecord) -> dict[str, object]:
        return {
            "document_id": record.document_id,
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "file_name": record.file_name,
            "file_size_bytes": record.file_size_bytes,
            "status": record.status,
            "stage": record.stage,
            "progress": record.progress,
            "error": record.error,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "processed_at": record.processed_at.isoformat() if record.processed_at else None,
            "processing_seconds": record.processing_seconds,
            "cached": record.cached,
            "page_count": record.page_count,
        }

    def _serialize_pages(self, pages: list[PageRecord]) -> list[dict[str, object]]:
        return [
            {
                "page_number": page.page_number,
                "text": page.text,
                "blocks": [
                    {
                        "kind": block.kind,
                        "text": block.text,
                        "page_number": block.page_number,
                    }
                    for block in page.blocks
                ],
            }
            for page in pages
        ]

    def _deserialize_pages(self, raw_pages: list[dict[str, object]]) -> list[PageRecord]:
        pages: list[PageRecord] = []
        for raw_page in raw_pages:
            blocks = [
                PageBlock(
                    kind=str(block.get("kind", "text")),
                    text=str(block.get("text", "")),
                    page_number=int(block.get("page_number", raw_page["page_number"])),
                )
                for block in raw_page.get("blocks", [])
            ]
            pages.append(
                PageRecord(
                    page_number=int(raw_page["page_number"]),
                    text=str(raw_page.get("text", "")),
                    blocks=blocks,
                )
            )
        return pages

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if value is None or not isinstance(value, str):
            return None
        return datetime.fromisoformat(value)


class AntipaperService:
    """Facade used by the FastAPI routes."""

    def __init__(self, artifact_root: Path | None = None) -> None:
        root = (artifact_root or Path(os.getenv("ARTIFACT_DIR", ".artifacts"))).expanduser()
        root = root.resolve()
        self.history = TaskHistoryStore(root / "history.sqlite3")
        self.store = DocumentStore(
            artifact_root=root,
            transition_listener=self._record_document_transition,
        )

    def submit_document(
        self,
        file_name: str,
        file_bytes: bytes,
        user_id: str = "demo-user",
    ) -> UploadResponse:
        # Create the activity row before validation/processing. This makes the
        # history a faithful audit of user actions: rejected uploads (for
        # example, unsupported extensions or oversized payloads) are still
        # represented as failed tasks even though no document_id exists.
        task = self.history.create_task(
            user_id=user_id,
            task_type="document_processing",
            display_name=file_name,
            status="queued",
            stage=STAGE_QUEUED,
            progress=0,
        )

        try:
            record, cached = self.store.submit_upload(file_name, file_bytes)
        except ApiError as exc:
            self.history.update_task(
                task.task_id,
                status="failed",
                stage=STAGE_FAILED,
                progress=100,
                error_code=exc.code,
                error_message=exc.message,
            )
            raise
        except Exception as exc:  # pragma: no cover - defensive persistence
            self.history.update_task(
                task.task_id,
                status="failed",
                stage=STAGE_FAILED,
                progress=100,
                error_code="PROCESSING_FAILED",
                error_message=str(exc),
            )
            raise

        error_code: str | None = None
        error_message: str | None = None
        if record.error:
            error_code, _, error_message = record.error.partition(": ")
        # Attach the document identity and reconcile any worker transitions.
        # The worker may finish between submit_upload and this callback, so the
        # reconciliation must always run after the task row exists.
        self.history.attach_document(
            task.task_id,
            document_id=record.document_id,
            cached=cached,
            error_code=error_code,
            error_message=error_message,
        )
        # Reconcile with the latest state in case the worker already advanced
        # through one or more transitions while the upload was being attached.
        self._record_document_transition(record)
        return UploadResponse(
            document_id=record.document_id,
            status=record.status,
            cached=cached,
            task_id=task.task_id,
        )

    def process_document(self, document_id: str) -> None:
        self.store.process_document(document_id)

    def get_status(self, document_id: str) -> StatusResponse:
        return self.store.get_status(document_id)

    def get_report(self, document_id: str) -> DocumentReport:
        return self.store.get_report(document_id)

    def get_page(self, document_id: str, page_number: int) -> PageResponse:
        return self.store.get_page(document_id, page_number)

    def answer_question(
        self,
        document_id: str,
        question: str,
        user_id: str = "demo-user",
    ) -> QuestionResponse:
        display_name = " ".join(question.split())[:160]
        task = self.history.create_task(
            user_id=user_id,
            task_type="question_answer",
            display_name=display_name,
            document_id=document_id,
            status="processing",
            stage="answering",
            progress=50,
        )
        try:
            response = self.store.answer_question(document_id, question)
        except ApiError as exc:
            self.history.update_task(
                task.task_id,
                status="failed",
                stage="failed",
                progress=100,
                error_code=exc.code,
                error_message=exc.message,
            )
            raise
        except Exception as exc:
            self.history.update_task(
                task.task_id,
                status="failed",
                stage="failed",
                progress=100,
                error_code="PROCESSING_FAILED",
                error_message=str(exc),
            )
            raise
        self.history.update_task(
            task.task_id,
            status="completed",
            stage="ready",
            progress=100,
            duration_seconds=response.latency_ms / 1000,
        )
        return response.model_copy(update={"task_id": task.task_id})

    def list_history(
        self,
        *,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        status: DocumentStatus | None = None,
        task_type: TaskType | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> TaskHistoryPage:
        return self.history.list_tasks(
            user_id=user_id,
            limit=limit,
            offset=offset,
            status=status,
            task_type=task_type,
            from_at=from_at,
            to_at=to_at,
        )

    def get_history(self, *, user_id: str, task_id: str) -> TaskHistoryItem:
        return self.history.get_task(user_id=user_id, task_id=task_id)

    def _record_document_transition(self, record: DocumentRecord) -> None:
        error_code: str | None = None
        error_message: str | None = None
        if record.error:
            error_code, _, error_message = record.error.partition(": ")
        duration = record.processing_seconds if record.status == "completed" else None
        self.history.update_open_document_tasks(
            document_id=record.document_id,
            status=record.status,
            stage=record.stage,
            progress=record.progress,
            error_code=error_code,
            error_message=error_message,
            duration_seconds=duration,
        )
