"""Stable data contracts for grounded meeting-intelligence generation.

The models in this module are deliberately independent from the ingestion
implementation.  The ingestion owner can replace the fixture with the real
``NormalizedDocument`` as long as the JSON shape remains compatible.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TermCategory = Literal[
    "defined_term",
    "legal_subject",
    "right_obligation",
    "procedure_condition",
    "sanction_dispute",
    "technical_concept",
]


class ContractModel(BaseModel):
    """Base model with predictable validation and JSON-schema generation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Citation(ContractModel):
    """Metadata used by a consumer to navigate back to source evidence."""

    page: int = Field(ge=1)
    chapter: str | None = None
    section: str | None = None
    article: str | None = None
    clause: str | None = None
    point: str | None = None
    excerpt: str = Field(min_length=1)


class DocumentChunk(ContractModel):
    """Smallest evidence unit that an LLM is allowed to cite."""

    chunk_id: str = Field(min_length=1)
    page: int = Field(ge=1)
    text: str = Field(min_length=1)
    chapter: str | None = None
    section: str | None = None
    article: str | None = None
    clause: str | None = None
    point: str | None = None


class NormalizedDocument(ContractModel):
    """Minimal normalized-document contract required by intelligence."""

    document_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    page_count: int = Field(ge=1)
    chunks: list[DocumentChunk]
    citations: dict[str, Citation] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_document_links(self) -> "NormalizedDocument":
        chunk_ids = [chunk.chunk_id for chunk in self.chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("chunk_id values must be unique")
        if self.chunks and max(chunk.page for chunk in self.chunks) > self.page_count:
            raise ValueError("chunk page cannot exceed page_count")
        unknown_citations = set(self.citations).difference(chunk_ids)
        if unknown_citations:
            raise ValueError(
                "citations keys must reference chunk_id values: "
                + ", ".join(sorted(unknown_citations))
            )
        return self

    @property
    def citation_whitelist(self) -> set[str]:
        """Return the authoritative IDs accepted in generated output."""

        return {chunk.chunk_id for chunk in self.chunks}


class EvidenceItem(ContractModel):
    """A generated statement backed by one or more document chunks."""

    text: str = Field(min_length=1)
    citation_ids: list[str] = Field(min_length=1)

    @field_validator("citation_ids")
    @classmethod
    def normalize_citation_ids(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not normalized:
            raise ValueError("at least one non-empty citation ID is required")
        return normalized


class IntelligenceSummary(ContractModel):
    """The four mandatory summary sections from the API contract."""

    context: list[EvidenceItem] = Field(default_factory=list)
    main_content: list[EvidenceItem] = Field(default_factory=list)
    decision_points: list[EvidenceItem] = Field(default_factory=list)
    impact: list[EvidenceItem] = Field(default_factory=list)


class TermExplanation(ContractModel):
    """A context-specific term explanation with direct source evidence."""

    term: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    citation_ids: list[str] = Field(min_length=1, max_length=2)
    category: TermCategory = "technical_concept"
    source_type: Literal["document_definition", "document_context", "official_reference"] = "document_context"
    importance_reason: str = ""
    external_sources: list[dict[str, Any]] = Field(default_factory=list)

    _normalize_citations = field_validator("citation_ids")(
        EvidenceItem.normalize_citation_ids.__func__
    )


class SuggestedQuestion(ContractModel):
    """A document-specific critical question and why it should be discussed."""

    question: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    citation_ids: list[str] = Field(min_length=1)
    rubric_score: int | None = Field(default=None, ge=0, le=4)

    _normalize_citations = field_validator("citation_ids")(
        EvidenceItem.normalize_citation_ids.__func__
    )


class IntelligenceDraft(ContractModel):
    """Structured output requested from both map and reduce LLM stages."""

    summary: IntelligenceSummary = Field(default_factory=IntelligenceSummary)
    terms: list[TermExplanation] = Field(default_factory=list, max_length=100)
    suggested_questions: list[SuggestedQuestion] = Field(default_factory=list)


class StageTiming(ContractModel):
    """Latency and call-count telemetry for one intelligence stage."""

    stage: str
    duration_ms: float = Field(ge=0)
    llm_calls: int = Field(ge=0)


class QualityResult(ContractModel):
    """Machine-checkable handoff checklist; human review remains authoritative."""

    required_summary_complete: bool
    term_count: int = Field(ge=0)
    question_count: int = Field(ge=0)
    questions_passing_rubric: int = Field(ge=0)
    citations_valid: bool
    passed: bool


class IntelligenceReport(IntelligenceDraft):
    """Validated report returned to API/orchestration consumers."""

    stage_timings: list[StageTiming] = Field(default_factory=list)
    quality: QualityResult


def coerce_normalized_document(document: Any) -> NormalizedDocument:
    """Validate dicts, Pydantic models, or dataclass-like ingestion objects."""

    if isinstance(document, NormalizedDocument):
        return document
    if isinstance(document, BaseModel):
        return NormalizedDocument.model_validate(document.model_dump())
    if isinstance(document, dict):
        return NormalizedDocument.model_validate(document)
    values = {
        field: getattr(document, field)
        for field in NormalizedDocument.model_fields
        if hasattr(document, field)
    }
    return NormalizedDocument.model_validate(values)
