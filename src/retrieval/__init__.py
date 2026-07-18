"""Small, dependency-free retrieval and grounded Q&A primitives."""

from .index import RetrievalIndex, RetrievalResult, build_index, build_index_async, meaningful_tokens
from .citations import CitationValidation, render_citations, validate_citations
from .qa import GroundedAnswer, GroundedQAService, answer
from .golden import CaseEvaluation, GoldenCase, GoldenEvaluation, evaluate_case, evaluate_golden_set, evaluate_golden_set_async, load_golden_cases
from .llm_adapter import GroundedLlmResponse, LlmRagAdapter, RETRIEVAL_QA_SYSTEM_PROMPT
from .related import (
    CatalogEntry,
    RelatedDocumentHit,
    extract_related_documents,
    load_related_catalog,
)

__all__ = [
    "CatalogEntry",
    "CitationValidation",
    "GroundedAnswer",
    "GroundedLlmResponse",
    "GroundedQAService",
    "CaseEvaluation",
    "GoldenCase",
    "GoldenEvaluation",
    "RelatedDocumentHit",
    "LlmRagAdapter",
    "RETRIEVAL_QA_SYSTEM_PROMPT",
    "RetrievalIndex",
    "RetrievalResult",
    "answer",
    "build_index",
    "build_index_async",
    "meaningful_tokens",
    "evaluate_case",
    "evaluate_golden_set",
    "evaluate_golden_set_async",
    "extract_related_documents",
    "load_golden_cases",
    "load_related_catalog",
    "render_citations",
    "validate_citations",
]
