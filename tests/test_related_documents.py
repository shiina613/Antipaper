from __future__ import annotations

from backend.intelligence import NormalizedDocument
from backend.related_documents import (
    RelatedDocumentFinder,
    TavilyResult,
    TavilySearchClient,
)


def make_document(text: str) -> NormalizedDocument:
    return NormalizedDocument.model_validate(
        {
            "document_id": "related-doc-test",
            "file_name": "meeting.pdf",
            "page_count": 2,
            "chunks": [
                {
                    "chunk_id": "P2-D1",
                    "page": 2,
                    "text": text,
                }
            ],
            "citations": {
                "P2-D1": {
                    "page": 2,
                    "excerpt": text[:100],
                }
            },
        }
    )


def test_extracts_and_deduplicates_explicit_legal_references() -> None:
    document = make_document(
        "Căn cứ Bộ luật Hình sự (100/2015/QH13), Bộ luật Tố tụng hình sự "
        "(101/2015/QH13) và Nghị định số 40/2020/NĐ-CP."
    )

    mentions = RelatedDocumentFinder().extract_mentions(document)

    assert [(item.title, item.document_number) for item in mentions] == [
        ("Bộ luật Hình sự", "100/2015/QH13"),
        ("Bộ luật Tố tụng hình sự", "101/2015/QH13"),
        ("Nghị định", "40/2020/NĐ-CP"),
    ]
    assert all(item.citation_id == "P2-D1" for item in mentions)


def test_no_explicit_reference_returns_empty_instead_of_placeholder() -> None:
    document = make_document(
        "Cuộc họp đánh giá tiến độ dự án và phân công trách nhiệm cho các đơn vị."
    )

    assert RelatedDocumentFinder().find(document) == []


def test_tavily_url_allowlist_rejects_unapproved_hosts() -> None:
    client = TavilySearchClient(
        api_key="test-key",
        allowed_domains=("gov.vn", "vnexpress.net"),
    )

    assert client.is_allowed_url("https://example.gov.vn/van-ban") is True
    assert client.is_allowed_url("https://vnexpress.net/phap-luat") is True
    assert client.is_allowed_url("https://sub.vnexpress.net/phap-luat") is True
    assert client.is_allowed_url("https://gov.vn.attacker.example/van-ban") is False
    assert client.is_allowed_url("https://example.com/van-ban") is False
    assert client.is_allowed_url("javascript:alert(1)") is False


class FakeSearchClient:
    def search(self, query: str) -> list[TavilyResult]:
        assert "100/2015/QH13" in query
        return [
            TavilyResult(
                title="Bộ luật Hình sự số 100/2015/QH13",
                url="https://example.gov.vn/bo-luat-hinh-su",
                content="Nội dung chính thức của Bộ luật Hình sự số 100/2015/QH13.",
                score=0.95,
            )
        ]


def test_enriches_mention_with_tavily_result_and_keeps_document_citation() -> None:
    document = make_document("Căn cứ Bộ luật Hình sự (100/2015/QH13) để xem xét.")
    finder = RelatedDocumentFinder(search_client=FakeSearchClient())  # type: ignore[arg-type]

    related = finder.find(document)

    assert len(related) == 1
    assert related[0].source == "tavily"
    assert related[0].url == "https://example.gov.vn/bo-luat-hinh-su"
    assert related[0].publisher == "example.gov.vn"
    assert related[0].citation_ids == ["P2-D1"]
