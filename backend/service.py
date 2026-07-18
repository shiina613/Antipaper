"""In-memory backend runtime for document upload and orchestration."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import hashlib
import os
import threading
import time
from pathlib import Path

from .errors import ApiError
from .orchestrator import DocumentOrchestrator, ProcessedDocument, StitchedPage
from .schemas import (
    DocumentReport,
    DocumentStatus,
    PageBlock,
    PageResponse,
    QuestionResponse,
    StatusResponse,
    UploadResponse,
)

try:
    from llm import LlmClient, LlmSettings, shared_limiter
    from retrieval import RetrievalIndex, build_index, build_index_async
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from src.llm import LlmClient, LlmSettings, shared_limiter
    from src.retrieval import RetrievalIndex, build_index, build_index_async


LOCAL_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
VERCEL_MAX_UPLOAD_BYTES = 4 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
PROCESSING_WAIT_TIMEOUT_SECONDS = 15.0
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


def is_vercel_runtime() -> bool:
    return os.getenv("VERCEL") == "1"


def runtime_upload_limit_bytes() -> int:
    return VERCEL_MAX_UPLOAD_BYTES if is_vercel_runtime() else LOCAL_MAX_UPLOAD_BYTES


def _configured_llm_client() -> object | None:
    """Create one shared client only when an API key is configured."""
    if not (os.getenv("OPENAI_API_KEY", "").strip() or os.getenv("LLM_API_KEY", "").strip()):
        return None
    try:
        return LlmClient(settings=LlmSettings.from_env())
    except Exception:
        return None


def _configured_embedding_client() -> object | None:
    if not (os.getenv("OPENAI_API_KEY", "").strip() or os.getenv("LLM_API_KEY", "").strip()):
        return None
    try:
        settings = LlmSettings.from_env()
        return LlmClient(settings=settings, limiter=shared_limiter(settings.max_concurrency))
    except Exception:
        return None
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
    retrieval_index: RetrievalIndex | None = field(default=None, repr=False, compare=False)
    semantic_rebuild_future: Future[None] | None = field(default=None, repr=False, compare=False)
    semantic_rebuild_needed: bool = field(default=False, repr=False, compare=False)
    semantic_rebuild_scheduled: bool = field(default=False, repr=False, compare=False)


class DocumentStore:
    """Thread-safe store and scheduler for uploaded documents."""

    def __init__(self, artifact_root: Path | None = None, llm_client: object | None = None, embedding_client: object | None = None, embedding_client_factory=None, embedding_settings=None) -> None:
        self._lock = threading.RLock()
        self._documents: dict[str, DocumentRecord] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="antipaper-job")
        self._orchestrator = DocumentOrchestrator(llm_client=llm_client)
        self.llm_enabled = llm_client is not None
        self._query_llm_client = llm_client
        self._embedding_settings = embedding_settings or getattr(embedding_client, "settings", None)
        if embedding_client_factory is not None:
            self._embedding_client_factory = embedding_client_factory
        elif embedding_client is not None and hasattr(embedding_client, "new_loop_local_embedding_client"):
            self._embedding_client_factory = embedding_client.new_loop_local_embedding_client
        else:
            self._embedding_client_factory = None
        if artifact_root is not None:
            root = artifact_root
        elif is_vercel_runtime():
            root = Path("/tmp/antipaper")
        else:
            root = Path(os.getenv("ARTIFACT_DIR", ".artifacts"))
        self._artifact_root = (root.expanduser() / "documents").resolve()
        self._artifact_root.mkdir(parents=True, exist_ok=True)

    def submit_upload(self, file_name: str, file_bytes: bytes) -> tuple[DocumentRecord, bool]:
        upload_limit = runtime_upload_limit_bytes()
        if len(file_bytes) > upload_limit:
            raise ApiError(
                code="FILE_TOO_LARGE",
                message=f"File too large. Maximum size is {upload_limit // (1024 * 1024)} MB.",
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
                if rehydrated.semantic_rebuild_needed:
                    self._schedule_rebuild(rehydrated)
                return rehydrated, True

            record = DocumentRecord(
                document_id=document_id,
                file_name=file_name,
                file_size_bytes=len(file_bytes),
                file_bytes=file_bytes,
            )
            self._documents[document_id] = record

        if is_vercel_runtime():
            self.process_document(record.document_id)
        else:
            self._start_processing(record)
        return record, False

    def ensure_processed(self, document_id: str) -> DocumentRecord:
        record = self.get(document_id)
        if record.status in {"queued", "processing"}:
            self._wait_for_completion(record)
        return self.get(document_id)

    def get(self, document_id: str) -> DocumentRecord:
        with self._lock:
            record = self._documents.get(document_id)
            if record is not None:
                return record

            rehydrated = self._rehydrate_from_artifacts(document_id)
            if rehydrated is not None:
                self._documents[document_id] = rehydrated
                if rehydrated.semantic_rebuild_needed:
                    self._schedule_rebuild(rehydrated)
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
            normalized = result.processed_document.normalized_document
            if normalized is not None:
                record.retrieval_index = build_index(normalized)
                if self._embedding_client_factory is not None:
                    try:
                        record.retrieval_index = asyncio.run(self._build_semantic_index(normalized))
                    except Exception:
                        record.semantic_rebuild_needed = False
            processing_seconds = round(time.perf_counter() - start, 3)
            record.processed_document = result.processed_document
            record.processed_document.processing_seconds = processing_seconds
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
            if record.semantic_rebuild_needed:
                self._schedule_rebuild(record)
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
        if record.processed_document is None:
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
        )

    async def answer_question(self, document_id: str, question: str) -> QuestionResponse:
        record = await asyncio.to_thread(self.ensure_processed, document_id)
        if record.processed_document is None:
            if record.status == "failed" and record.error:
                raise self._api_error_from_record_error(record.error)
            raise ApiError(
                code="PROCESSING_FAILED",
                message="Document is not ready for question answering.",
                status_code=409,
                retryable=True,
            )
        start = time.perf_counter()
        index = record.retrieval_index
        if index is None and record.processed_document.normalized_document is not None:
            index = build_index(record.processed_document.normalized_document)
            record.retrieval_index = index
        response = await self._orchestrator.answer_question(
            record.processed_document,
            question,
            retrieval_index=index,
            query_embedder=getattr(self._query_llm_client, "embed", None) if index is not None and getattr(index, "_vectors", None) else None,
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return response.model_copy(update={"latency_ms": latency_ms})

    async def _build_semantic_index(self, normalized):
        worker_client = self._embedding_client_factory() if self._embedding_client_factory is not None else None
        embed = getattr(worker_client, "embed", None)
        settings = getattr(worker_client, "settings", None) or self._embedding_settings
        if embed is None or settings is None or not getattr(settings, "embedding_model", ""):
            raise RuntimeError("embedding client unavailable")
        self._embedding_settings = settings
        batch_size = getattr(getattr(worker_client, "settings", None), "embedding_max_batch_size", 64)
        candidate = await build_index_async(normalized, embed, batch_size=batch_size)
        expected = self._expected_embedding_dimension(worker_client)
        if expected is not None and any(len(vector) != expected for vector in candidate._vectors.values()):
            raise ValueError("embedding dimension mismatch")
        return candidate

    def _expected_embedding_dimension(self, client=None) -> int | None:
        settings = getattr(client, "settings", None) or self._embedding_settings
        configured = getattr(settings, "embedding_dimensions", None)
        if configured is not None:
            return configured
        if getattr(settings, "embedding_model", None) == "text-embedding-3-small":
            return 1536
        return None

    def _schedule_rebuild(self, record: DocumentRecord) -> None:
        with self._lock:
            if self._embedding_client_factory is None or record.semantic_rebuild_future is not None or record.semantic_rebuild_scheduled:
                return
            record.semantic_rebuild_scheduled = True
            record.semantic_rebuild_future = self._executor.submit(self._rebuild_semantic, record.document_id)

    def _rebuild_semantic(self, document_id: str) -> None:
        record = self.get(document_id)
        normalized = record.processed_document.normalized_document if record.processed_document else None
        try:
            if normalized is None:
                return
            candidate = asyncio.run(self._build_semantic_index(normalized))
            with self._lock:
                if self._documents.get(document_id) is record:
                    record.retrieval_index = candidate
                    record.semantic_rebuild_needed = False
                    self._persist_semantic_artifact(record)
        except Exception:
            with self._lock:
                if self._documents.get(document_id) is record:
                    record.semantic_rebuild_needed = False
            return
        finally:
            with self._lock:
                if self._documents.get(document_id) is record:
                    record.semantic_rebuild_future = None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _start_processing(self, record: DocumentRecord) -> None:
        record.status = "queued"
        record.stage = STAGE_QUEUED
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
        record.stage = STAGE_FAILED
        record.progress = 100
        record.error = f"{code}: {message}"
        record.updated_at = datetime.now(timezone.utc)
        self._persist_artifacts(record)

    def _validate_orchestration_result(
        self,
        record: DocumentRecord,
        result: object,
    ) -> None:
        if not hasattr(result, "processed_document") or not hasattr(result, "report"):
            raise ValueError("Orchestrator returned an invalid result object.")

        processed_document = getattr(result, "processed_document")
        report = getattr(result, "report")
        if processed_document is None or report is None:
            raise ValueError("Orchestrator returned empty processing output.")

        if getattr(report, "document_id", None) != record.document_id:
            raise ValueError("Report document_id does not match the uploaded document.")
        if getattr(report, "page_count", None) != getattr(processed_document, "page_count", None):
            raise ValueError("Report page_count does not match the processed document.")

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

    def _semantic_path(self, document_id: str) -> Path:
        return self._artifact_dir(document_id) / "semantic_index.v1.json"

    def _normalized_path(self, document_id: str) -> Path:
        return self._artifact_dir(document_id) / "normalized_document.v1.json"

    def _persist_artifacts(self, record: DocumentRecord) -> None:
        try:
            artifact_dir = self._artifact_dir(record.document_id)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            self._manifest_path(record.document_id).write_text(
                json.dumps(self._serialize_manifest(record), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if record.status == "completed" and record.processed_document is not None and record.processed_document.normalized_document is not None:
                self._persist_normalized_artifact(record)
            if record.status == "completed" and record.report is not None:
                self._pages_path(record.document_id).write_text(
                    json.dumps(self._serialize_pages(record.pages), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self._report_path(record.document_id).write_text(
                    record.report.model_dump_json(indent=2),
                    encoding="utf-8",
                )
                self._persist_semantic_artifact(record)
        except Exception:  # pragma: no cover - artifact persistence is best effort
            return

    def _persist_normalized_artifact(self, record: DocumentRecord) -> None:
        normalized = record.processed_document.normalized_document
        payload = {
            "schema_version": 1,
            "document_sha256": record.document_id,
            "normalized_document": normalized.model_dump(mode="json"),
        }
        path = self._normalized_path(record.document_id)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        temp.replace(path)

    def _persist_semantic_artifact(self, record: DocumentRecord) -> None:
        index = record.retrieval_index
        normalized = record.processed_document.normalized_document if record.processed_document else None
        if index is None or not getattr(index, "_vectors", None) or normalized is None:
            return
        vectors = {chunk_id: list(vector) for chunk_id, vector in index._vectors.items()}
        payload = {
            "schema_version": 1,
            "preprocessing_version": "retrieval-v1",
            "document_sha256": record.document_id,
            "document_id": normalized.document_id,
            "file_name": normalized.file_name,
            "model": getattr(self._embedding_settings, "embedding_model", None),
            "dimension": len(next(iter(vectors.values()))) if vectors else 0,
            "chunk_ids": [chunk.chunk_id for chunk in normalized.chunks],
            "text_hashes": {chunk.chunk_id: hashlib.sha256(chunk.text.encode("utf-8")).hexdigest() for chunk in normalized.chunks},
            "normalized_document": normalized.model_dump(mode="json"),
            "vectors": vectors,
        }
        path = self._semantic_path(record.document_id)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        temp.replace(path)

    def _rehydrate_from_artifacts(self, document_id: str) -> DocumentRecord | None:
        manifest_path = self._manifest_path(document_id)
        report_path = self._report_path(document_id)
        pages_path = self._pages_path(document_id)
        normalized_path = self._normalized_path(document_id)
        if not manifest_path.exists():
            return None

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = DocumentRecord(
                document_id=document_id,
                file_name=str(manifest["file_name"]),
                file_size_bytes=int(manifest["file_size_bytes"]),
                file_bytes=b"",
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
            manifest_hash = manifest.get("file_sha256", document_id)
            if manifest_hash != document_id:
                return None
            if record.status == "completed":
                if not report_path.exists() or not pages_path.exists() or not normalized_path.exists():
                    return None
                record.report = DocumentReport.model_validate_json(report_path.read_text(encoding="utf-8"))
                record.pages = self._deserialize_pages(json.loads(pages_path.read_text(encoding="utf-8")))
                record.processed_document = ProcessedDocument(
                    source_name=record.file_name,
                    page_count=record.page_count,
                    stitched_pages=[
                        StitchedPage(page_number=page.page_number, content=page.text)
                        for page in record.pages
                    ],
                )
                from intelligence import NormalizedDocument
                normalized_payload = json.loads(normalized_path.read_text(encoding="utf-8"))
                if normalized_payload.get("document_sha256") != document_id or normalized_payload.get("schema_version") != 1:
                    return None
                normalized = NormalizedDocument.model_validate(normalized_payload["normalized_document"])
                record.processed_document.normalized_document = normalized
                record.retrieval_index = build_index(normalized)
                semantic_path = self._semantic_path(document_id)
                semantic_valid = False
                if semantic_path.exists():
                    try:
                        semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
                        if semantic.get("schema_version") != 1 or semantic.get("preprocessing_version") != "retrieval-v1":
                            raise ValueError("semantic schema mismatch")
                        normalized = NormalizedDocument.model_validate(semantic["normalized_document"])
                        if semantic.get("document_sha256") != document_id:
                            raise ValueError("semantic record hash mismatch")
                        if semantic["document_id"] != normalized.document_id or semantic["file_name"] != normalized.file_name:
                            raise ValueError("semantic document identity mismatch")
                        if normalized.model_dump(mode="json") != record.processed_document.normalized_document.model_dump(mode="json"):
                            raise ValueError("semantic canonical normalized document mismatch")
                        expected_model = getattr(self._embedding_settings, "embedding_model", None)
                        if expected_model is not None and semantic.get("model") != expected_model:
                            raise ValueError("semantic model mismatch")
                        expected_dimension = self._expected_embedding_dimension()
                        if expected_dimension is not None and semantic.get("dimension") != expected_dimension:
                            raise ValueError("semantic dimension mismatch")
                        hashes = {chunk.chunk_id: hashlib.sha256(chunk.text.encode("utf-8")).hexdigest() for chunk in normalized.chunks}
                        if semantic["chunk_ids"] != [chunk.chunk_id for chunk in normalized.chunks] or semantic["text_hashes"] != hashes:
                            raise ValueError("semantic text identity mismatch")
                        if semantic["dimension"] != len(next(iter(semantic["vectors"].values()))):
                            raise ValueError("semantic dimension mismatch")
                        record.retrieval_index = build_index(normalized, vectors=semantic["vectors"])
                        semantic_valid = True
                    except Exception:
                        semantic_valid = False
                if not semantic_valid:
                    record.semantic_rebuild_needed = self._embedding_client_factory is not None
            return record
        except Exception:  # pragma: no cover - corrupted artifacts are treated as cache miss
            return None

    def _serialize_manifest(self, record: DocumentRecord) -> dict[str, object]:
        return {
            "document_id": record.document_id,
            "file_sha256": record.document_id,
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

    def __init__(self, artifact_root: Path | None = None, llm_client: object | None = None, embedding_client: object | None = None, embedding_client_factory=None, embedding_settings=None) -> None:
        configured = llm_client if llm_client is not None else _configured_llm_client()
        configured_embedding = embedding_client if embedding_client is not None else (None if embedding_client_factory is not None else _configured_embedding_client())
        self.store = DocumentStore(artifact_root=artifact_root, llm_client=configured, embedding_client=configured_embedding, embedding_client_factory=embedding_client_factory, embedding_settings=embedding_settings)

    @property
    def llm_status(self) -> str:
        return "configured" if self.store.llm_enabled else "disabled"

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

    async def answer_question(self, document_id: str, question: str) -> QuestionResponse:
        return await self.store.answer_question(document_id, question)

    def shutdown(self) -> None:
        self.store.shutdown()
