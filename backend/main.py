"""FastAPI entry point for the Antipaper backend skeleton."""

from __future__ import annotations

import re
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .errors import register_error_handlers
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
async def document_question(
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
        return "uploaded-file", await request.body()

    boundary_match = re.search(r"boundary=([^;]+)", content_type)
    if boundary_match is None:
        return "uploaded-file", await request.body()

    boundary = boundary_match.group(1).strip().strip('"')
    body = await request.body()
    delimiter = f"--{boundary}".encode()
    parts = body.split(delimiter)

    for raw_part in parts:
        part = raw_part.strip()
        if not part or part == b"--":
            continue

        header_blob, separator, content = part.partition(b"\r\n\r\n")
        if not separator:
            continue

        headers = _parse_headers(header_blob.decode("utf-8", errors="ignore"))
        disposition = headers.get("content-disposition", "")
        if 'name="file"' not in disposition:
            continue

        file_name = _parse_filename(disposition) or "uploaded-file"
        file_bytes = content.rstrip(b"\r\n")
        return file_name, file_bytes

    return "uploaded-file", body


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
