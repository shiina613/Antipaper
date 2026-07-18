"""Meeting intelligence features built on top of extracted document text."""

from .builder import (
    IntelligenceBuilder,
    IntelligenceConfigurationError,
    IntelligenceGenerationError,
    build_intelligence,
)
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
    TermExplanation,
)
from .meeting_intelligence import (
    GroundedAnswer,
    MeetingIntelligenceEngine,
    MeetingIntelligenceReport,
    MeetingSummary,
    SuggestedQuestion as LegacySuggestedQuestion,
    TermExplanation as LegacyTermExplanation,
)

__all__ = [
    "GroundedAnswer",
    "Citation",
    "DocumentChunk",
    "EvidenceItem",
    "IntelligenceBuilder",
    "IntelligenceConfigurationError",
    "IntelligenceDraft",
    "IntelligenceGenerationError",
    "IntelligenceReport",
    "IntelligenceSummary",
    "MeetingIntelligenceEngine",
    "MeetingIntelligenceReport",
    "MeetingSummary",
    "LegacySuggestedQuestion",
    "LegacyTermExplanation",
    "NormalizedDocument",
    "QualityResult",
    "StageTiming",
    "SuggestedQuestion",
    "TermExplanation",
    "build_intelligence",
]
