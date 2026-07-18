"""Small, dependency-free retrieval and grounded Q&A primitives."""

from .index import RetrievalIndex, RetrievalResult, build_index
from .citations import CitationValidation, render_citations, validate_citations
from .qa import GroundedAnswer, GroundedQAService, answer
from .golden import CaseEvaluation, GoldenCase, GoldenEvaluation, evaluate_case, evaluate_golden_set, evaluate_golden_set_async, load_golden_cases
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
    "GroundedQAService",
    "CaseEvaluation",
    "GoldenCase",
    "GoldenEvaluation",
    "RelatedDocumentHit",
    "RetrievalIndex",
    "RetrievalResult",
    "answer",
    "build_index",
    "evaluate_case",
    "evaluate_golden_set",
    "evaluate_golden_set_async",
    "extract_related_documents",
    "load_golden_cases",
    "load_related_catalog",
    "render_citations",
    "validate_citations",
]
