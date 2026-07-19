from __future__ import annotations

import asyncio
from pathlib import Path
import threading
import time

import pytest
from pydantic import BaseModel

from src.errors import ApiError
from src.ingestion import StitchedPage
import src.integrations.llm as llm_module
from src.integrations.llm import LlmClient, LlmSettings
from src.intelligence import DocumentChunk, NormalizedDocument
from src.intelligence.llm_pipeline import LlmIntelligencePipeline, LlmPipelineSettings, ProcessingDeadlineExceeded
from src.services.documents import AntipaperService
from src.services.orchestrator import AnalysisTextLimitExceeded, DocumentOrchestrator


class _NoopLlm:
    async def call(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        await asyncio.sleep(0.2)
        raise AssertionError("deadline should cancel before this response is used")


def _document(*, chunks: int = 4, text_size: int = 60) -> NormalizedDocument:
    return NormalizedDocument(
        document_id="sla",
        file_name="sla.pdf",
        page_count=chunks,
        chunks=[
            DocumentChunk(chunk_id=f"P{index}-D1", page=index, text="Nội dung có nghĩa vụ. " + "x" * text_size)
            for index in range(1, chunks + 1)
        ],
    )


def test_map_deadline_cancels_work_instead_of_posthoc_failure() -> None:
    settings = LlmPipelineSettings(
        map_batch_chars=100,
        map_max_batch_chars=100,
        map_target_batches=1,
        map_concurrency=1,
        map_budget_seconds=0.05,
        reduce_budget_seconds=0.01,
        questions_budget_seconds=0.01,
        reserve_seconds=0.01,
    )
    pipeline = LlmIntelligencePipeline(_NoopLlm(), settings)

    with pytest.raises(ProcessingDeadlineExceeded, match="mapping"):
        asyncio.run(pipeline.generate(_document(chunks=1), deadline_seconds=0.09))


def test_adaptive_batching_covers_all_chunks_of_08_within_six_batches() -> None:
    from src.ingestion import DocumentIngestor

    source = Path("data/08.pdf")
    document, _ = DocumentIngestor().ingest_bytes(
        document_id="08-sla", file_name=source.name, file_bytes=source.read_bytes()
    )
    pipeline = LlmIntelligencePipeline(
        _NoopLlm(),
        LlmPipelineSettings(
            map_batch_chars=24_000,
            map_max_batch_chars=100_000,
            map_target_batches=6,
            map_concurrency=3,
        ),
    )
    batches = list(pipeline._batches(document.chunks))

    assert len(batches) <= 6
    assert [chunk.chunk_id for batch in batches for chunk in batch] == [chunk.chunk_id for chunk in document.chunks]


def test_text_limit_rejects_before_any_llm_call(monkeypatch: pytest.MonkeyPatch) -> None:
    class Ingestor:
        def ingest_bytes(self, **_kwargs):  # noqa: ANN003
            document = _document(chunks=1, text_size=2_000)
            return document, [StitchedPage(page_number=1, content=document.chunks[0].text)]

    monkeypatch.setattr("src.services.orchestrator.MAX_ANALYZABLE_TEXT_CHARS", 100)
    orchestrator = DocumentOrchestrator(ingestor=Ingestor(), llm=_NoopLlm())

    with pytest.raises(AnalysisTextLimitExceeded):
        orchestrator.process(document_id="too-large", file_name="too-large.pdf", file_bytes=b"pdf")


class _SleepingIngestor:
    def __init__(self, seconds: float) -> None:
        self._seconds = seconds

    def ingest_bytes(self, **_kwargs):  # noqa: ANN003
        time.sleep(self._seconds)
        document = _document(chunks=1)
        return document, [StitchedPage(page_number=1, content=document.chunks[0].text)]


def test_slow_ingestion_within_budget_is_not_killed(monkeypatch: pytest.MonkeyPatch) -> None:
    # A parse slower than the old flat 10s cap must proceed once the configurable ingestion
    # budget allows it, instead of dying with a "during ingestion" deadline error.
    monkeypatch.setattr("src.services.orchestrator.INGESTION_DEADLINE_SECONDS", 5.0)
    orchestrator = DocumentOrchestrator(ingestor=_SleepingIngestor(0.2), llm=_NoopLlm())

    # The noop LLM asserts it is reached, proving ingestion did not short-circuit the run.
    with pytest.raises(AssertionError):
        orchestrator.process(document_id="slow-parse", file_name="slow.pdf", file_bytes=b"pdf")


def test_ingestion_budget_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Lowering the budget below the parse time still guards against runaway ingestion.
    monkeypatch.setattr("src.services.orchestrator.INGESTION_DEADLINE_SECONDS", 0.05)
    orchestrator = DocumentOrchestrator(ingestor=_SleepingIngestor(0.2), llm=_NoopLlm())

    with pytest.raises(ProcessingDeadlineExceeded, match="ingestion"):
        orchestrator.process(document_id="too-slow", file_name="slow.pdf", file_bytes=b"pdf")


def test_report_request_does_not_block_while_worker_is_processing(tmp_path: Path) -> None:
    class SlowOrchestrator:
        llm_enabled = True

        def process(self, **_kwargs):  # noqa: ANN003
            time.sleep(0.2)
            raise ProcessingDeadlineExceeded("Processing deadline exceeded during mapping.")

    service = AntipaperService(history_path=tmp_path / "history.sqlite3")
    service.store._related_document_finder = None
    service.store._orchestrator = SlowOrchestrator()
    upload = service.submit_document("sample.pdf", b"%PDF-1.4", user_id="test")

    started = time.perf_counter()
    with pytest.raises(ApiError) as error:
        service.get_report(upload.document_id)
    assert time.perf_counter() - started < 0.05
    assert error.value.code == "DOCUMENT_PROCESSING"
    service.shutdown()


def test_global_deadline_has_its_own_error_code(tmp_path: Path) -> None:
    class DeadlineOrchestrator:
        llm_enabled = True

        def process(self, **_kwargs):  # noqa: ANN003
            raise ProcessingDeadlineExceeded("Processing deadline exceeded during reduce.")

    service = AntipaperService(history_path=tmp_path / "history.sqlite3")
    service.store._related_document_finder = None
    service.store._orchestrator = DeadlineOrchestrator()
    upload = service.submit_document("sample.pdf", b"%PDF-1.4", user_id="test")

    for _ in range(100):
        status = service.get_status(upload.document_id)
        if status.status == "failed":
            break
        time.sleep(0.01)
    assert status.error and status.error.code == "GLOBAL_DEADLINE_EXCEEDED"
    service.shutdown()


def test_global_llm_limiter_bounds_concurrent_worker_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response(BaseModel):
        value: int

    active = 0
    observed_maximum = 0

    async def fake_call(self, payload, response_model, **_kwargs):  # noqa: ANN001
        nonlocal active, observed_maximum
        active += 1
        observed_maximum = max(observed_maximum, active)
        await asyncio.sleep(0.02)
        active -= 1
        return response_model(value=1)

    monkeypatch.setattr(llm_module, "_LIMITER", threading.BoundedSemaphore(1))
    monkeypatch.setattr(llm_module, "_LIMITER_CAPACITY", 1)
    monkeypatch.setattr(LlmClient, "_call_with_limiter", fake_call)
    client = LlmClient(LlmSettings(api_url="https://example.test", api_key="test", model="test"))

    async def run() -> None:
        await asyncio.gather(*(client.call([], Response) for _ in range(3)))

    asyncio.run(run())
    assert observed_maximum == 1
