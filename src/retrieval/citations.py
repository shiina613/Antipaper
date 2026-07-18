"""Fail-closed, request-scoped citation validation and rendering."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..intelligence.contracts import Citation, NormalizedDocument, coerce_normalized_document


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _excerpt_is_source(excerpt: str, source: str) -> bool:
    """Accept source-leading excerpts despite terminal punctuation differences."""
    # Ingestion deliberately caps excerpts by character count, which can end in
    # the middle of a word. A normalized character-prefix check preserves that
    # safe truncation without weakening the requirement that the excerpt starts
    # at the beginning of the authoritative chunk.
    normalized_excerpt = _normalize_text(excerpt).rstrip(".…").rstrip()
    if normalized_excerpt and _normalize_text(source).startswith(normalized_excerpt):
        return True
    excerpt_words = excerpt.casefold().split()
    source_words = source.casefold().split()
    if source_words[: len(excerpt_words)] == excerpt_words:
        return True
    # Punctuation can differ at sentence boundaries; compare normalized words.
    import re
    excerpt_tokens = re.findall(r"\w+", excerpt.casefold())
    source_tokens = re.findall(r"\w+", source.casefold())
    return bool(excerpt_tokens) and source_tokens[: len(excerpt_tokens)] == excerpt_tokens


@dataclass(frozen=True)
class CitationValidation:
    citations: tuple[Citation, ...]
    citation_ids: tuple[str, ...]
    invalid_reasons: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.invalid_reasons

    def __iter__(self):
        return iter(self.citations)

    def __len__(self) -> int:
        return len(self.citations)


def validate_citations(ids: Any, document: NormalizedDocument, retrieved_ids: Any = None) -> CitationValidation:
    doc = coerce_normalized_document(document)
    if not isinstance(ids, list):
        return CitationValidation((), (), ("citation IDs must be a list",))
    if retrieved_ids is not None and not isinstance(retrieved_ids, (list, tuple, set)):
        return CitationValidation((), (), ("retrieved IDs must be a list",))
    retrieved = set(retrieved_ids) if retrieved_ids is not None else None
    seen: set[str] = set()
    ordered_ids: list[str] = []
    valid: list[Citation] = []
    reasons: list[str] = []
    for raw in ids:
        value = raw.strip() if isinstance(raw, str) else ""
        if not value:
            reasons.append("blank citation ID")
        elif value in seen:
            reasons.append(f"duplicate citation ID: {value}")
        elif value not in doc.citation_whitelist:
            reasons.append(f"unknown citation ID: {value}")
        elif retrieved is not None and value not in retrieved:
            reasons.append(f"citation not retrieved: {value}")
        else:
            seen.add(value)
            ordered_ids.append(value)
            chunk = next(c for c in doc.chunks if c.chunk_id == value)
            citation = doc.citations.get(value)
            if citation is not None and any(getattr(citation, field) != getattr(chunk, field) for field in ("page", "chapter", "article", "clause")):
                reasons.append(f"inconsistent citation metadata: {value}")
                ordered_ids.pop()
                continue
            if citation is not None and not _excerpt_is_source(citation.excerpt, chunk.text):
                reasons.append(f"inconsistent citation excerpt: {value}")
                ordered_ids.pop()
                continue
            if citation is None:
                citation = Citation(page=chunk.page, chapter=chunk.chapter, article=chunk.article, clause=chunk.clause, excerpt=chunk.text)
            valid.append(citation)
    return CitationValidation(tuple(valid), tuple(ordered_ids), tuple(reasons))


def render_citations(validation: CitationValidation | list[str], document: NormalizedDocument | None = None, retrieved_ids: Any = None) -> list[dict[str, object]]:
    if not isinstance(validation, CitationValidation):
        if document is None:
            raise TypeError("document required when rendering citation IDs")
        validation = validate_citations(validation, document, retrieved_ids)
    return [{"citation_id": cid, **citation.model_dump()} for cid, citation in zip(validation.citation_ids, validation.citations)]
