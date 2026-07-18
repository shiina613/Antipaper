"""FastAPI entry point for the Antipaper backend skeleton."""

from __future__ import annotations

import re
import time
from tempfile import SpooledTemporaryFile

from fastapi import FastAPI, Request
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
    UploadResponse,
)
from .service import AntipaperService
from . import __version__

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


app = FastAPI(
    title="Antipaper API",
    version=__version__,
    description="Backend skeleton for document upload, status, report, pages, and Q&A.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
service = AntipaperService()
configure_logging()
logger = get_logger("http")


@app.get("/")
@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "antipaper-backend",
        "version": __version__,
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
) -> UploadResponse:
    file_name, file_bytes = await _extract_upload(request)
    return service.submit_document(file_name, file_bytes)


@app.get("/api/v1/documents/{document_id}/status", response_model=StatusResponse)
async def document_status(document_id: str) -> StatusResponse:
    return service.get_status(document_id)


@app.get("/api/v1/documents/{document_id}/report", response_model=DocumentReport)
async def document_report(document_id: str) -> DocumentReport:
    return service.get_report(document_id)


@app.post("/api/v1/documents/{document_id}/questions", response_model=QuestionResponse)
def document_question(
    document_id: str,
    body: QuestionRequest,
) -> QuestionResponse:
    return service.answer_question(document_id, body.question)


@app.get("/api/v1/documents/{document_id}/pages/{page_number}", response_model=PageResponse)
async def document_page(document_id: str, page_number: int) -> PageResponse:
    return service.get_page(document_id, page_number)


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
