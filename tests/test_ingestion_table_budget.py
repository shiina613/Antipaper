"""Table detection must never let native PDF parsing run away.

`page.find_tables()` is the dominant, GIL-bound cost of ingestion; on a slow CPU it turned a
99-page document's parse into 83s and blew the ingestion budget. Detection is now bounded by a
per-document time budget while text (every chunk and citation) is always fully extracted.
"""
from __future__ import annotations

from pathlib import Path
import time

import pytest

from src.ingestion.document_ingestor import DocumentIngestor, IngestionOptions


_SAMPLE = Path("data/03.pdf")  # 99-page text-heavy legal PDF: the reported failure case.


def test_zero_budget_skips_table_detection_but_keeps_text(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def spy(self: DocumentIngestor, page: object) -> str:  # noqa: ANN001
        calls.append(1)
        return ""

    monkeypatch.setattr(DocumentIngestor, "_extract_native_tables_markdown", spy)
    ingestor = DocumentIngestor(IngestionOptions(table_extraction_budget_seconds=0.0))

    document, _ = ingestor.ingest_bytes(
        document_id="no-tables", file_name=_SAMPLE.name, file_bytes=_SAMPLE.read_bytes()
    )

    assert calls == []  # a zero budget must not even attempt detection
    assert document.page_count == 99
    assert any(chunk.text.strip() for chunk in document.chunks)  # text is unaffected


def test_table_detection_stops_once_budget_is_spent(monkeypatch: pytest.MonkeyPatch) -> None:
    attempted: list[int] = []

    def slow(self: DocumentIngestor, page: object) -> str:  # noqa: ANN001
        attempted.append(1)
        time.sleep(0.05)
        return ""

    monkeypatch.setattr(DocumentIngestor, "_extract_native_tables_markdown", slow)
    ingestor = DocumentIngestor(IngestionOptions(table_extraction_budget_seconds=0.1))

    document, _ = ingestor.ingest_bytes(
        document_id="budgeted", file_name=_SAMPLE.name, file_bytes=_SAMPLE.read_bytes()
    )

    # ~0.1s budget at 0.05s/page: a few pages are scanned, not all 99, yet every page is
    # still read for text.
    assert 0 < len(attempted) < document.page_count
    assert document.page_count == 99


def test_default_ingestion_stays_well_under_the_deadline() -> None:
    started = time.perf_counter()
    document, _ = DocumentIngestor().ingest_bytes(
        document_id="default", file_name=_SAMPLE.name, file_bytes=_SAMPLE.read_bytes()
    )
    elapsed = time.perf_counter() - started

    assert document.page_count == 99
    # Text (1.8s) plus a bounded ~8s of table detection must leave ample room under the 45s
    # ingestion budget even before the CPU is contended.
    assert elapsed < 20.0
