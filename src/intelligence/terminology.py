"""Deterministic, evidence-first extraction of legal terminology."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable, Sequence

from .contracts import NormalizedDocument, TermExplanation


MAX_TERMS = 500
MAX_IMPLICIT_TERMS = 20

_GLOSSARY_TITLE = re.compile(r"\bgiải\s+thích\s+từ\s+ngữ\b|\bđược\s+hiểu\s+như\s+sau\b", re.IGNORECASE)
_ARTICLE = re.compile(r"^\s*Điều\s+\d+[a-zA-Z]?\b", re.IGNORECASE)
_DEFINITION = re.compile(
    r"^\s*(?P<number>\d{1,3})[.)]\s*(?P<term>.{2,180}?)\s+"
    r"(?:là|được\s+hiểu\s+là|bao\s+gồm)\s+(?P<body>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_LEGAL_SIGNAL = re.compile(
    r"\b(có quyền|có nghĩa vụ|nghĩa vụ|quyền|không được|cấm|bị cấm|"
    r"điều kiện|thủ tục|trình tự|xử phạt|chế tài|tranh chấp|vi phạm|"
    r"người lao động|người sử dụng lao động|cơ quan|tổ chức|pháp nhân|"
    r"hợp đồng|thỏa ước|đại diện)\b",
    re.IGNORECASE,
)
_IMPACT_SIGNAL = re.compile(r"\b(quyền|nghĩa vụ|trách nhiệm|cấm|xử phạt|tranh chấp|vi phạm)\b", re.IGNORECASE)
_GENERIC_TERMS = {
    "quyết định",
    "trách nhiệm",
    "tác động",
    "quốc hội",
    "văn bản",
    "dự thảo",
    "nghị định",
    "thông tư",
    "điều",
    "chương",
    "mục",
}

_TERM_CATEGORIES = {
    "defined_term",
    "legal_subject",
    "right_obligation",
    "procedure_condition",
    "sanction_dispute",
    "technical_concept",
}


@dataclass(frozen=True)
class CandidateTerm:
    """A model-selected candidate that still needs deterministic validation."""

    term: str
    category: str
    selection_reason: str
    legal_salience: int
    reader_difficulty: int
    citation_ids: list[str]
    explanation: str


@dataclass(frozen=True)
class TerminologyResult:
    terms: list[TermExplanation]
    status: str
    explicit_detected: int
    explicit_returned: int
    implicit_returned: int
    generic_rejected: int
    warnings: list[str]


@dataclass
class _OpenDefinition:
    term: str
    body_parts: list[str]
    citation_ids: list[str]


def normalize_text(value: str) -> str:
    """Normalize source text without changing legal meaning."""

    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value or "")).strip()


def extract_explicit_definitions(document: NormalizedDocument) -> list[TermExplanation]:
    """Extract all numbered definitions from glossary articles, including page breaks."""

    extracted: list[TermExplanation] = []
    open_definition: _OpenDefinition | None = None
    in_glossary = False
    glossary_article: str | None = None

    def finish() -> None:
        nonlocal open_definition
        if open_definition is None:
            return
        explanation = normalize_text(" ".join(open_definition.body_parts))
        if explanation and open_definition.citation_ids:
            extracted.append(
                TermExplanation(
                    term=normalize_text(open_definition.term),
                    explanation=explanation,
                    citation_ids=open_definition.citation_ids[:2],
                    category="defined_term",
                    source_type="document_definition",
                    importance_reason="Thuật ngữ được tài liệu định nghĩa trực tiếp.",
                )
            )
        open_definition = None

    for chunk in document.chunks:
        text = normalize_text(chunk.text)
        article = normalize_text(chunk.article or "") or None
        is_article_boundary = bool(_ARTICLE.match(text)) or (article is not None and article != glossary_article)
        if _GLOSSARY_TITLE.search(text):
            finish()
            in_glossary = True
            glossary_article = article
        elif in_glossary and is_article_boundary:
            finish()
            in_glossary = False
            glossary_article = None

        if not in_glossary:
            continue

        match = _DEFINITION.match(text)
        if match:
            finish()
            open_definition = _OpenDefinition(
                term=match.group("term"),
                body_parts=[match.group("body")],
                citation_ids=[chunk.chunk_id],
            )
        elif open_definition is not None:
            open_definition.body_parts.append(text)
            if chunk.chunk_id not in open_definition.citation_ids:
                open_definition.citation_ids.append(chunk.chunk_id)

    finish()
    return _deduplicate_explicit(extracted)


def build_terminology_result(
    document: NormalizedDocument,
    candidates: Sequence[CandidateTerm] = (),
    *,
    implicit_analysis_available: bool,
    warnings: Iterable[str] = (),
) -> TerminologyResult:
    """Combine mandatory document definitions with validated implicit concepts."""

    explicit = extract_explicit_definitions(document)
    warning_codes = list(dict.fromkeys(warnings))
    if len(explicit) > MAX_TERMS:
        warning_codes.append("TERM_LIMIT_EXCEEDED")
    explicit_returned = explicit[:MAX_TERMS]
    implicit, generic_rejected = _validated_implicit_candidates(
        document,
        candidates,
        explicit_returned,
        capacity=max(0, MAX_TERMS - len(explicit_returned)),
    )
    if len(explicit) > MAX_TERMS or not implicit_analysis_available:
        status = "partial"
    else:
        status = "complete"
    if not document.chunks:
        status = "unavailable"
        warning_codes.append("NO_USABLE_TEXT")
    return TerminologyResult(
        terms=[*explicit_returned, *implicit],
        status=status,
        explicit_detected=len(explicit),
        explicit_returned=len(explicit_returned),
        implicit_returned=len(implicit),
        generic_rejected=generic_rejected,
        warnings=warning_codes,
    )


def _deduplicate_explicit(items: Sequence[TermExplanation]) -> list[TermExplanation]:
    seen: set[str] = set()
    kept: list[TermExplanation] = []
    for item in items:
        key = _term_key(item.term)
        if key and key not in seen:
            seen.add(key)
            kept.append(item)
    return kept


def _validated_implicit_candidates(
    document: NormalizedDocument,
    candidates: Sequence[CandidateTerm],
    explicit: Sequence[TermExplanation],
    *,
    capacity: int,
) -> tuple[list[TermExplanation], int]:
    chunks = {chunk.chunk_id: chunk for chunk in document.chunks}
    existing = {_term_key(item.term) for item in explicit}
    accepted: list[tuple[float, TermExplanation]] = []
    rejected_generic = 0

    for candidate in candidates:
        term = normalize_text(candidate.term)
        key = _term_key(term)
        if not key or key in existing or key in _GENERIC_TERMS:
            rejected_generic += 1
            continue
        citation_ids = list(dict.fromkeys(cid for cid in candidate.citation_ids if cid in chunks))[:2]
        evidence = " ".join(normalize_text(chunks[cid].text) for cid in citation_ids)
        if not citation_ids or term.casefold() not in evidence.casefold() or not _LEGAL_SIGNAL.search(evidence):
            continue
        if candidate.legal_salience < 50 or candidate.reader_difficulty < 35:
            continue
        occurrence_count = sum(term.casefold() in normalize_text(chunk.text).casefold() for chunk in document.chunks)
        centrality = min(100, round(100 * occurrence_count / max(1, len(document.chunks))))
        impact = 100 if _IMPACT_SIGNAL.search(evidence) else 50
        score = (
            0.35 * candidate.legal_salience
            + 0.30 * candidate.reader_difficulty
            + 0.20 * centrality
            + 0.15 * impact
        )
        explanation = normalize_text(candidate.explanation) or normalize_text(candidate.selection_reason)
        if not explanation:
            continue
        accepted.append(
            (
                score,
                TermExplanation(
                    term=term,
                    explanation=explanation,
                    citation_ids=citation_ids,
                    category=_normalize_category(candidate.category, term, evidence),
                    source_type="document_context",
                    importance_reason=normalize_text(candidate.selection_reason),
                ),
            )
        )
        existing.add(key)

    accepted.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in accepted[: min(MAX_IMPLICIT_TERMS, capacity)]], rejected_generic


def _normalize_category(category: str, term: str, evidence: str) -> str:
    """Return a public enum value even when a non-strict provider localizes labels."""

    raw = normalize_text(category).casefold().replace("-", "_").replace(" ", "_")
    if raw in _TERM_CATEGORIES:
        return raw

    localized = normalize_text(category).casefold()
    if any(value in localized for value in ("thủ tục", "trình tự", "điều kiện", "hồ sơ", "cấp phép")):
        return "procedure_condition"
    if any(value in localized for value in ("xử phạt", "chế tài", "vi phạm", "tranh chấp", "khiếu nại")):
        return "sanction_dispute"
    if any(value in localized for value in ("cơ quan", "tổ chức", "cá nhân", "người lao động", "chủ thể")):
        return "legal_subject"
    if any(value in localized for value in ("quyền", "nghĩa vụ", "trách nhiệm", "bổn phận")):
        return "right_obligation"
    if any(value in localized for value in ("định nghĩa", "giải thích từ ngữ", "khái niệm được hiểu")):
        return "defined_term"

    signals = f"{term} {evidence}".casefold()
    if any(value in signals for value in ("định nghĩa", "giải thích từ ngữ", "khái niệm được hiểu")):
        return "defined_term"
    if any(value in signals for value in ("thủ tục", "trình tự", "điều kiện", "hồ sơ", "cấp phép")):
        return "procedure_condition"
    if any(value in signals for value in ("xử phạt", "chế tài", "vi phạm", "tranh chấp", "khiếu nại")):
        return "sanction_dispute"
    if any(value in signals for value in ("quyền", "nghĩa vụ", "trách nhiệm", "bổn phận")):
        return "right_obligation"
    if any(value in signals for value in ("cơ quan", "tổ chức", "cá nhân", "người lao động", "chủ thể")):
        return "legal_subject"
    return "technical_concept"


def _term_key(value: str) -> str:
    return normalize_text(value).casefold().strip(" .,:;()[]{}\"'")
