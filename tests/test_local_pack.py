from __future__ import annotations

from intelligence.contracts import Citation, DocumentChunk, NormalizedDocument
from intelligence.local_pack import build_local_intelligence_pack


def test_local_pack_meets_minimum_terms_and_questions() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="P1-D1",
            page=1,
            text=(
                "Luật này quy định chế độ hôn nhân và gia đình; kết hôn và ly hôn "
                "phải tuân thủ căn cứ pháp lý. Ủy ban nhân dân có trách nhiệm thực hiện."
            ),
            article="Điều 1",
        ),
        DocumentChunk(
            chunk_id="P2-D2",
            page=2,
            text=(
                "An ninh mạng và an toàn thông tin mạng bảo vệ hệ thống thông tin "
                "quan trọng về an ninh quốc gia trên không gian mạng. Không được vi phạm."
            ),
            article="Điều 2",
        ),
        DocumentChunk(
            chunk_id="P3-D3",
            page=3,
            text=(
                "Quyết định xử lý vi phạm hành chính phải đánh giá tác động và rủi ro. "
                "Nuôi con nuôi theo luật định."
            ),
            article="Điều 3",
        ),
    ]
    document = NormalizedDocument(
        document_id="pack01",
        file_name="demo.pdf",
        page_count=3,
        chunks=chunks,
        citations={
            chunk.chunk_id: Citation(
                page=chunk.page,
                article=chunk.article,
                excerpt=chunk.text[:100],
            )
            for chunk in chunks
        },
    )

    pack = build_local_intelligence_pack(document)
    assert len(pack.terms) >= 10
    assert all(term.citation_ids for term in pack.terms)
    assert len(pack.suggested_questions) >= 5
    assert all(question.citation_ids for question in pack.suggested_questions)
    assert all((question.rubric_score or 0) >= 3 for question in pack.suggested_questions)
