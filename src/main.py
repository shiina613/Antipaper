"""FastAPI entry point for the Antipaper backend skeleton."""

from __future__ import annotations

from datetime import datetime
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Header, Query, Request, UploadFile
from dotenv import load_dotenv
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
    DocumentStatus,
    TaskHistoryItem,
    TaskHistoryPage,
    TaskType,
    UploadResponse,
)
from .services.documents import AntipaperService
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
    logger.warning("LLM report generation is disabled; document reports will fail closed.")


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
    file: UploadFile = File(...),
    user_id: str = Header(
        default="demo-user",
        alias="X-User-ID",
        min_length=1,
        max_length=128,
        pattern=USER_ID_PATTERN,
    ),
) -> UploadResponse:
    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    return service.submit_document(file.filename or "uploaded-file", file_bytes, user_id=user_id)


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


@app.delete("/api/v1/history/{task_id}", status_code=204, response_class=Response)
async def delete_task_history(
    task_id: str,
    user_id: str = Header(
        default="demo-user",
        alias="X-User-ID",
        min_length=1,
        max_length=128,
        pattern=USER_ID_PATTERN,
    ),
) -> Response:
    service.delete_history(user_id=user_id, task_id=task_id)
    return Response(status_code=204)


@app.delete("/api/v1/history/sessions/{document_id}", status_code=204, response_class=Response)
async def delete_history_session(
    document_id: str,
    user_id: str = Header(
        default="demo-user",
        alias="X-User-ID",
        min_length=1,
        max_length=128,
        pattern=USER_ID_PATTERN,
    ),
) -> Response:
    service.delete_history_session(user_id=user_id, document_id=document_id)
    return Response(status_code=204)


