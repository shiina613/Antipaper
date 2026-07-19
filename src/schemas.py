"""Pydantic models for the Antipaper API contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


DocumentStatus = Literal["queued", "processing", "completed", "failed"]
TaskType = Literal["document_processing", "question_answer"]


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: ErrorDetail


class UploadResponse(BaseModel):
    document_id: str
    status: DocumentStatus
    task_id: str | None = None


class StatusResponse(BaseModel):
    document_id: str
    status: DocumentStatus
    stage: str = Field(default="queued")
    progress: int = Field(default=0, ge=0, le=100)
    elapsed_seconds: float = Field(default=0.0, ge=0.0)
    error: ErrorDetail | None = None


class Citation(BaseModel):
    page: int = Field(ge=1)
    chapter: str | None = None
    article: str | None = None
    clause: str | None = None
    excerpt: str


class SummaryItem(BaseModel):
    text: str
    citation_ids: list[str] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    context: list[SummaryItem] = Field(default_factory=list)
    main_content: list[SummaryItem] = Field(default_factory=list)
    decision_points: list[SummaryItem] = Field(default_factory=list)
    impact: list[SummaryItem] = Field(default_factory=list)


class TermItem(BaseModel):
    term: str
    explanation: str
    citation_ids: list[str] = Field(default_factory=list)
    category: Literal[
        "defined_term",
        "legal_subject",
        "right_obligation",
        "procedure_condition",
        "sanction_dispute",
        "technical_concept",
    ] = "technical_concept"
    source_type: Literal["document_definition", "document_context", "official_reference"] = "document_context"
    importance_reason: str = ""
    external_sources: list[dict[str, Any]] = Field(default_factory=list)


class TerminologyQuality(BaseModel):
    status: Literal["complete", "partial", "unavailable"]
    explicit_detected: int = Field(ge=0)
    explicit_returned: int = Field(ge=0)
    implicit_returned: int = Field(ge=0)
    generic_rejected: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class StageTiming(BaseModel):
    """Latency telemetry for one bounded processing stage."""

    stage: str
    duration_ms: float = Field(ge=0.0)


class ReportQuality(BaseModel):
    pipeline: str
    map_batch_count: int = Field(ge=0)
    question_count: int = Field(ge=0)
    summary_sections_complete: bool
    citations_valid: bool
    report_status: Literal["complete", "partial"]
    passed: bool
    terminology: TerminologyQuality
    input_characters: int = Field(default=0, ge=0)
    map_wave_count: int = Field(default=0, ge=0)
    llm_call_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    queue_ms: float = Field(default=0.0, ge=0.0)
    stage_timings: list[StageTiming] = Field(default_factory=list)


class SuggestedQuestion(BaseModel):
    question: str
    rationale: str
    citation_ids: list[str] = Field(default_factory=list)


class RelatedDocument(BaseModel):
    title: str
    document_number: str = ""
    mentioned_name: str | None = None
    source: str
    reason: str
    citation_ids: list[str] = Field(default_factory=list)
    url: str | None = None
    publisher: str | None = None
    excerpt: str | None = None


class DocumentReport(BaseModel):
    document_id: str
    file_name: str
    page_count: int = Field(ge=1)
    processing_seconds: float = Field(ge=0.0)
    summary: DocumentSummary
    terms: list[TermItem] = Field(default_factory=list, max_length=500)
    suggested_questions: list[SuggestedQuestion] = Field(default_factory=list)
    related_documents: list[RelatedDocument] = Field(default_factory=list)
    citations: dict[str, Citation] = Field(default_factory=dict)
    generation_mode: Literal["llm", "terminology_partial"] = "llm"
    quality: ReportQuality
    enrichment_status: Literal["not_configured", "pending", "completed", "failed"] = "not_configured"


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class QuestionResponse(BaseModel):
    answer: str
    insufficient_evidence: bool
    citation_ids: list[str] = Field(default_factory=list)
    latency_ms: float = Field(ge=0.0)
    task_id: str | None = None


class PageBlock(BaseModel):
    kind: str = "text"
    text: str
    page_number: int = Field(ge=1)


class SourcePreview(BaseModel):
    kind: Literal["page_image"] = "page_image"
    mime_type: str
    data_url: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    page_number: int = Field(ge=1)


class PageResponse(BaseModel):
    document_id: str
    page_number: int = Field(ge=1)
    text: str
    blocks: list[PageBlock] = Field(default_factory=list)
    source_preview: SourcePreview | None = None


class TaskHistoryError(BaseModel):
    code: str
    message: str


class TaskHistoryItem(BaseModel):
    task_id: str
    task_type: TaskType
    document_id: str | None = None
    display_name: str
    status: DocumentStatus
    stage: str
    progress: int = Field(ge=0, le=100)
    created_at: datetime
    started_at: datetime | None = None
    updated_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = Field(default=None, ge=0.0)
    error: TaskHistoryError | None = None


class TaskHistoryPage(BaseModel):
    items: list[TaskHistoryItem] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)

