"""Deterministic intelligence contracts and heuristic report helpers."""

from .contracts import (
    Citation,
    DocumentChunk,
    EvidenceItem,
    IntelligenceDraft,
    IntelligenceReport,
    IntelligenceSummary,
    NormalizedDocument,
    QualityResult,
    StageTiming,
    SuggestedQuestion,
    TermCategory,
    TermExplanation,
)
from .local_pack import LocalIntelligencePack, build_local_intelligence_pack, detect_terms, suggest_questions
from .terminology import CandidateTerm, TerminologyResult, build_terminology_result, extract_explicit_definitions
from .llm_pipeline import IntelligenceQualityError, LlmIntelligencePipeline, LlmIntelligenceResult, LlmPipelineSettings

__all__ = [
    "Citation", "DocumentChunk", "EvidenceItem", "IntelligenceDraft", "IntelligenceReport",
    "IntelligenceSummary", "LocalIntelligencePack", "NormalizedDocument", "QualityResult",
    "StageTiming", "SuggestedQuestion", "TermCategory", "TermExplanation", "IntelligenceQualityError",
    "LlmIntelligencePipeline", "LlmIntelligenceResult", "LlmPipelineSettings", "build_local_intelligence_pack",
    "detect_terms", "suggest_questions",
    "CandidateTerm", "TerminologyResult", "build_terminology_result", "extract_explicit_definitions",
]
