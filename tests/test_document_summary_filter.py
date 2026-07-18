from __future__ import annotations

from intelligence.contracts import Citation, DocumentChunk, NormalizedDocument
from summary.document_summary import DocumentSummary, DocumentSummaryEngine, SummaryItem


def test_filter_keeps_text_when_citations_are_invented() -> None:
    engine = DocumentSummaryEngine()
    summary = DocumentSummary(
        context=[
            SummaryItem(text="Bối cảnh quan trọng", citation_ids=["FAKE-ID"]),
        ],
        main_content=[
            SummaryItem(text="Nội dung chính", citation_ids=[]),
        ],
    )
    filtered = engine._filter_invalid_citations(
        summary,
        whitelist={"P1-D1"},
        preferred_ids={"P1-D1"},
        fallback_chunk_id="P1-D1",
    )
    assert filtered.context[0].text == "Bối cảnh quan trọng"
    assert filtered.context[0].citation_ids == ["P1-D1"]
    assert filtered.main_content[0].citation_ids == ["P1-D1"]


def test_merge_fills_empty_sections_from_rule_based() -> None:
    engine = DocumentSummaryEngine()
    document = NormalizedDocument(
        document_id="s1",
        file_name="demo.pdf",
        page_count=1,
        chunks=[
            DocumentChunk(
                chunk_id="P1-D1",
                page=1,
                text="Luật quy định trách nhiệm của cơ quan và tác động tới người dân.",
            )
        ],
        citations={"P1-D1": Citation(page=1, excerpt="Luật quy định")},
    )
    empty = DocumentSummary()
    fallback = engine.build(document)
    merged = engine._merge_with_fallback(empty, fallback)
    assert merged.context
    assert merged.main_content or merged.impact or merged.decision_points
