"""Extract related legal documents from chunk text and a local catalog.

TA-04: never invent related acts. Prefer citations found in the uploaded
document, then enrich metadata from ``related_documents_catalog.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable

try:
    from intelligence.contracts import DocumentChunk, NormalizedDocument
except ModuleNotFoundError:
    from src.intelligence.contracts import DocumentChunk, NormalizedDocument


DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "fixtures" / "related_documents_catalog.json"
)

_DOC_NUMBER_RE = re.compile(
    r"(?P<label>"
    r"Luật(?:\s+[A-ZÀ-Ỵ][\wÀ-ỹ]*(?:\s+[\wÀ-ỹ]+){0,8})?\s+số(?:\s*:)?|"
    r"Nghị\s+quyết\s+số|"
    r"Nghị\s+định\s+số|"
    r"Thông\s+tư\s+số|"
    r"Quyết\s+định\s+số|"
    r"Bộ\s+luật(?:\s+[\wÀ-ỹ]+){0,4}\s+số"
    r")\s*(?P<number>\d{1,3}/\d{4}/[A-Z0-9]+)",
    re.IGNORECASE,
)

_NAMED_LAW_RE = re.compile(
    r"\b(?P<title>"
    r"Luật\s+An\s+ninh\s+mạng|"
    r"Luật\s+An\s+toàn\s+thông\s+tin\s+mạng|"
    r"Luật\s+Hôn\s+nhân\s+và\s+gia\s+đình|"
    r"Luật\s+nuôi\s+con\s+nuôi|"
    r"Luật\s+Xử\s+lý\s+vi\s+phạm\s+hành\s+chính|"
    r"Luật\s+Giao\s+dịch\s+điện\s+tử|"
    r"Luật\s+Dữ\s+liệu|"
    r"Luật\s+Viễn\s+thông|"
    r"Luật\s+Lưu\s+trữ|"
    r"Bộ\s+luật\s+[Dd]ân\s+sự|"
    r"Bộ\s+luật\s+[Hh]ình\s+sự|"
    r"Bộ\s+luật\s+[Tt]ố\s+tụng\s+hình\s+sự"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CatalogEntry:
    title: str
    document_number: str
    aliases: tuple[str, ...]
    url: str | None = None
    issued_date: str | None = None
    status: str | None = None
    fetched_at: str | None = None


@dataclass(frozen=True)
class RelatedDocumentHit:
    title: str
    document_number: str
    source: str
    reason: str
    citation_ids: list[str]
    url: str | None = None
    catalog_matched: bool = False


def load_related_catalog(path: str | Path | None = None) -> list[CatalogEntry]:
    catalog_path = Path(path) if path else DEFAULT_CATALOG_PATH
    if not catalog_path.exists():
        return []
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    entries: list[CatalogEntry] = []
    for item in raw:
        entries.append(
            CatalogEntry(
                title=str(item["title"]).strip(),
                document_number=str(item["document_number"]).strip(),
                aliases=tuple(str(alias).strip() for alias in item.get("aliases", []) if str(alias).strip()),
                url=item.get("url"),
                issued_date=item.get("issued_date"),
                status=item.get("status"),
                fetched_at=item.get("fetched_at"),
            )
        )
    return entries


def extract_related_documents(
    document: NormalizedDocument | Any,
    *,
    catalog: Iterable[CatalogEntry] | None = None,
    catalog_path: str | Path | None = None,
    limit: int = 12,
) -> list[RelatedDocumentHit]:
    """Return related docs mentioned in the document, enriched by local catalog."""

    chunks = _chunks_from(document)
    if not chunks:
        return []

    entries = list(catalog) if catalog is not None else load_related_catalog(catalog_path)
    by_number = {entry.document_number.lower(): entry for entry in entries}
    by_alias = {}
    for entry in entries:
        by_alias[_normalize(entry.title)] = entry
        for alias in entry.aliases:
            by_alias[_normalize(alias)] = entry

    collected: dict[str, RelatedDocumentHit] = {}
    for chunk in chunks:
        text = chunk.text or ""
        for match in _DOC_NUMBER_RE.finditer(text):
            number = match.group("number").strip()
            label = re.sub(r"\s+", " ", match.group(0)).strip()
            entry = by_number.get(number.lower())
            key = number.lower()
            hit = collected.get(key)
            if hit is None:
                collected[key] = RelatedDocumentHit(
                    title=entry.title if entry else label,
                    document_number=entry.document_number if entry else number,
                    source="catalog" if entry else "cited_in_document",
                    reason=f"Được nhắc trực tiếp trong tài liệu: {label}.",
                    citation_ids=[chunk.chunk_id],
                    url=entry.url if entry else None,
                    catalog_matched=entry is not None,
                )
            elif chunk.chunk_id not in hit.citation_ids:
                collected[key] = RelatedDocumentHit(
                    title=hit.title,
                    document_number=hit.document_number,
                    source=hit.source,
                    reason=hit.reason,
                    citation_ids=[*hit.citation_ids, chunk.chunk_id],
                    url=hit.url,
                    catalog_matched=hit.catalog_matched,
                )

        for match in _NAMED_LAW_RE.finditer(text):
            title = re.sub(r"\s+", " ", match.group("title")).strip()
            entry = by_alias.get(_normalize(title))
            if entry is None:
                continue
            key = entry.document_number.lower()
            hit = collected.get(key)
            if hit is None:
                collected[key] = RelatedDocumentHit(
                    title=entry.title,
                    document_number=entry.document_number,
                    source="catalog",
                    reason=f"Tên văn bản được nhắc trong tài liệu: {title}.",
                    citation_ids=[chunk.chunk_id],
                    url=entry.url,
                    catalog_matched=True,
                )
            elif chunk.chunk_id not in hit.citation_ids:
                collected[key] = RelatedDocumentHit(
                    title=hit.title,
                    document_number=hit.document_number,
                    source=hit.source,
                    reason=hit.reason,
                    citation_ids=[*hit.citation_ids, chunk.chunk_id],
                    url=hit.url,
                    catalog_matched=hit.catalog_matched,
                )

    ranked = sorted(
        collected.values(),
        key=lambda item: (-int(item.catalog_matched), -len(item.citation_ids), item.document_number),
    )
    return ranked[:limit]


def _chunks_from(document: NormalizedDocument | Any) -> list[DocumentChunk]:
    if isinstance(document, NormalizedDocument):
        return list(document.chunks)
    chunks = getattr(document, "chunks", None) or []
    result: list[DocumentChunk] = []
    for chunk in chunks:
        if isinstance(chunk, DocumentChunk):
            result.append(chunk)
            continue
        chunk_id = getattr(chunk, "chunk_id", None)
        page = getattr(chunk, "page", None) or getattr(chunk, "page_number", None)
        text = getattr(chunk, "text", None)
        if chunk_id and page and text:
            result.append(
                DocumentChunk(
                    chunk_id=str(chunk_id),
                    page=int(page),
                    text=str(text),
                    chapter=getattr(chunk, "chapter", None),
                    section=getattr(chunk, "section", None),
                    article=getattr(chunk, "article", None),
                    clause=getattr(chunk, "clause", None),
                    point=getattr(chunk, "point", None),
                )
            )
    return result


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()
