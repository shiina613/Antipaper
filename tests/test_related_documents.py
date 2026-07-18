from __future__ import annotations

from intelligence.contracts import Citation, DocumentChunk, NormalizedDocument
from retrieval.related import extract_related_documents, load_related_catalog


def _document_with_text(text: str) -> NormalizedDocument:
    chunk = DocumentChunk(chunk_id="P1-D1", page=1, text=text, article="Điều 1")
    return NormalizedDocument(
        document_id="demo01",
        file_name="demo.pdf",
        page_count=1,
        chunks=[chunk],
        citations={
            "P1-D1": Citation(page=1, article="Điều 1", excerpt=text[:120]),
        },
    )


def test_catalog_loads_entries() -> None:
    catalog = load_related_catalog()
    assert len(catalog) >= 5
    assert any(entry.document_number == "24/2018/QH14" for entry in catalog)


def test_extract_related_documents_matches_catalog_by_number() -> None:
    document = _document_with_text(
        "Căn cứ Luật An ninh mạng số 24/2018/QH14 và Luật An toàn thông tin mạng số 86/2015/QH13."
    )
    hits = extract_related_documents(document)
    numbers = {hit.document_number for hit in hits}
    assert "24/2018/QH14" in numbers
    assert "86/2015/QH13" in numbers
    assert all(hit.citation_ids for hit in hits)
    assert any(hit.catalog_matched for hit in hits)


def test_extract_related_documents_matches_named_law() -> None:
    document = _document_with_text(
        "Quan hệ hôn nhân được điều chỉnh theo Luật Hôn nhân và gia đình và Bộ luật dân sự."
    )
    hits = extract_related_documents(document)
    titles = " ".join(hit.title.casefold() for hit in hits)
    assert "hôn nhân" in titles or "dân sự" in titles
    assert all(hit.source in {"catalog", "cited_in_document"} for hit in hits)


def test_extract_related_documents_does_not_invent_when_absent() -> None:
    document = _document_with_text("Tài liệu này không nhắc số hiệu văn bản nào.")
    hits = extract_related_documents(document)
    assert hits == []
