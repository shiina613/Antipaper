"""FastAPI entry point for the Antipaper backend skeleton."""

from __future__ import annotations

from datetime import datetime
import re
import time
from contextlib import asynccontextmanager
from tempfile import SpooledTemporaryFile

from fastapi import FastAPI, Header, Query, Request
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .errors import ApiError, register_error_handlers
from .logging import configure_logging, get_logger
from .schemas import (
    DocumentReport,
    PageResponse,
    QuestionRequest,
    QuestionResponse,
    StatusResponse,
    DocumentStatus,
    TaskHistoryItem,
    TaskHistoryPage,
    TaskType,
    UploadResponse,
)
from .service import AntipaperService
from . import __version__

load_dotenv()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
USER_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    service.shutdown()


app = FastAPI(
    title="Antipaper API",
    version=__version__,
    description="Backend skeleton for document upload, status, report, pages, and Q&A.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

configure_logging()
logger = get_logger("http")
register_error_handlers(app)
service = AntipaperService()
if service.llm_status == "disabled":
    logger.warning("LLM RAG is disabled; using grounded extractive fallback.")


@app.get("/")
@app.get("/health")
@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "antipaper-backend",
        "version": __version__,
        "llm_status": service.llm_status,
    }


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    content_length = request.headers.get("content-length", "unknown")
    logger.info(
        "%s %s -> %s (%sms, content_length=%s)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        content_length,
    )
    return response


@app.post("/api/v1/documents", response_model=UploadResponse, status_code=202)
async def upload_document(
    request: Request,
    user_id: str = Header(
        default="demo-user",
        alias="X-User-ID",
        min_length=1,
        max_length=128,
        pattern=USER_ID_PATTERN,
    ),
) -> UploadResponse:
    file_name, file_bytes = await _extract_upload(request)
    return service.submit_document(file_name, file_bytes, user_id=user_id)


@app.get("/api/v1/documents/{document_id}/status", response_model=StatusResponse)
async def document_status(document_id: str) -> StatusResponse:
    return service.get_status(document_id)


@app.get("/api/v1/documents/{document_id}/report", response_model=DocumentReport)
async def document_report(document_id: str) -> DocumentReport:
    return service.get_report(document_id)


@app.post("/api/v1/documents/{document_id}/questions", response_model=QuestionResponse)
async def document_question(
    document_id: str,
    body: QuestionRequest,
    user_id: str = Header(
        default="demo-user",
        alias="X-User-ID",
        min_length=1,
        max_length=128,
        pattern=USER_ID_PATTERN,
    ),
) -> QuestionResponse:
    return await service.answer_question(document_id, body.question, user_id=user_id)


@app.get("/api/v1/documents/{document_id}/pages/{page_number}", response_model=PageResponse)
async def document_page(document_id: str, page_number: int) -> PageResponse:
    return service.get_page(document_id, page_number)


@app.get("/api/v1/history", response_model=TaskHistoryPage)
async def task_history(
    user_id: str = Header(
        default="demo-user",
        alias="X-User-ID",
        min_length=1,
        max_length=128,
        pattern=USER_ID_PATTERN,
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: DocumentStatus | None = Query(default=None),
    task_type: TaskType | None = Query(default=None),
    from_at: datetime | None = Query(default=None),
    to_at: datetime | None = Query(default=None),
) -> TaskHistoryPage:
    return service.list_history(
        user_id=user_id,
        limit=limit,
        offset=offset,
        status=status,
        task_type=task_type,
        from_at=from_at,
        to_at=to_at,
    )


@app.get("/api/v1/history/{task_id}", response_model=TaskHistoryItem)
async def task_history_detail(
    task_id: str,
    user_id: str = Header(
        default="demo-user",
        alias="X-User-ID",
        min_length=1,
        max_length=128,
        pattern=USER_ID_PATTERN,
    ),
) -> TaskHistoryItem:
    return service.get_history(user_id=user_id, task_id=task_id)


async def _extract_upload(request: Request) -> tuple[str, bytes]:
    """Parse the single uploaded file from a multipart body without extras."""

    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        return "uploaded-file", await _read_stream_body(request)

    boundary_match = re.search(r"boundary=([^;]+)", content_type)
    if boundary_match is None:
        return "uploaded-file", await _read_stream_body(request)

    boundary = boundary_match.group(1).strip().strip('"')
    return await _read_multipart_file(request, boundary)


async def _read_stream_body(request: Request) -> bytes:
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
    return bytes(chunks)


async def _read_multipart_file(request: Request, boundary: str) -> tuple[str, bytes]:
    delimiter = f"--{boundary}".encode()
    header_terminator = b"\r\n\r\n"
    closing_delimiter = b"\r\n" + delimiter + b"--"
    next_part_delimiter = b"\r\n" + delimiter
    max_buffer = max(len(delimiter), len(closing_delimiter), len(next_part_delimiter)) + 8

    buffer = bytearray()
    file_name = "uploaded-file"
    seen_headers = False
    file_stream = SpooledTemporaryFile(max_size=1_048_576)
    file_size = 0

    async for chunk in request.stream():
        buffer.extend(chunk)

        if not seen_headers:
            boundary_index = buffer.find(delimiter)
            if boundary_index < 0:
                if len(buffer) > max_buffer:
                    del buffer[:-max_buffer]
                continue

            header_start = boundary_index + len(delimiter)
            if buffer[header_start:header_start + 2] == b"\r\n":
                header_start += 2

            header_end = buffer.find(header_terminator, header_start)
            if header_end < 0:
                continue

            header_blob = buffer[header_start:header_end].decode("utf-8", errors="ignore")
            headers = _parse_headers(header_blob)
            disposition = headers.get("content-disposition", "")
            if 'name="file"' not in disposition:
                buffer.clear()
                continue

            file_name = _parse_filename(disposition) or "uploaded-file"
            seen_headers = True
            del buffer[: header_end + len(header_terminator)]

        if not seen_headers:
            continue

        boundary_index = buffer.find(next_part_delimiter)
        closing_index = buffer.find(closing_delimiter)
        split_index = -1
        if closing_index >= 0 and (boundary_index < 0 or closing_index < boundary_index):
            split_index = closing_index
        elif boundary_index >= 0:
            split_index = boundary_index

        if split_index >= 0:
            file_bytes = bytes(buffer[:split_index].rstrip(b"\r\n"))
            file_stream.write(file_bytes)
            file_size += len(file_bytes)
            if file_size > MAX_UPLOAD_BYTES:
                file_stream.close()
                raise ApiError(
                    code="FILE_TOO_LARGE",
                    message="File too large. Maximum size is 25 MB.",
                    status_code=413,
                    retryable=False,
                )
            file_stream.seek(0)
            return file_name, file_stream.read()

        safe_write_upto = max(0, len(buffer) - max_buffer)
        if safe_write_upto > 0:
            file_chunk = bytes(buffer[:safe_write_upto])
            file_stream.write(file_chunk)
            file_size += len(file_chunk)
            if file_size > MAX_UPLOAD_BYTES:
                file_stream.close()
                raise ApiError(
                    code="FILE_TOO_LARGE",
                    message="File too large. Maximum size is 25 MB.",
                    status_code=413,
                    retryable=False,
                )
            del buffer[:safe_write_upto]

    if seen_headers:
        file_chunk = bytes(buffer.rstrip(b"\r\n"))
        file_stream.write(file_chunk)
        file_size += len(file_chunk)
        if file_size > MAX_UPLOAD_BYTES:
            file_stream.close()
            raise ApiError(
                code="FILE_TOO_LARGE",
                message="File too large. Maximum size is 25 MB.",
                status_code=413,
                retryable=False,
            )
        file_stream.seek(0)
        return file_name, file_stream.read()

    return "uploaded-file", bytes(buffer)


def _parse_headers(header_text: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in header_text.split("\r\n"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def _parse_filename(disposition: str) -> str | None:
    match = re.search(r'filename="([^"]+)"', disposition)
    if match is None:
        return None
    return match.group(1)
