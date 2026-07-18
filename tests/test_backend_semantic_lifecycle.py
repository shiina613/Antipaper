from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import threading
import time

from backend.orchestrator import ProcessedDocument, StitchedPage
from backend.schemas import DocumentReport, DocumentSummary
from backend.service import AntipaperService, DocumentRecord
from intelligence import NormalizedDocument
from retrieval import build_index


ROOT = Path(__file__).parents[1]


def document() -> NormalizedDocument:
    payload = json.loads((ROOT / "docs/fixtures/normalized_document.mock.json").read_text(encoding="utf-8"))
    return NormalizedDocument.model_validate(payload)


class Worker:
    def __init__(self, calls, failure=False, started=None):
        self.calls = calls
        self.failure = failure
        self.started = started
        self.settings = SimpleNamespace(embedding_model="fake-embedding", embedding_dimensions=2, embedding_max_batch_size=64)

    async def embed(self, texts):
        self.calls.append(len(texts))
        if self.started:
            self.started.set()
        if self.failure:
            raise RuntimeError("fake embedding failure")
        return [[1.0, 0.0] for _ in texts]


def make_service(tmp_path, factory, query_client=None):
    return AntipaperService(
        artifact_root=tmp_path,
        llm_client=query_client,
        embedding_client_factory=factory,
        embedding_settings=SimpleNamespace(embedding_model="fake-embedding", embedding_dimensions=2, embedding_max_batch_size=64),
    )


def install_record(service, semantic=True):
    doc = document()
    record_id = "a" * 64
    processed = ProcessedDocument(doc.file_name, doc.page_count, [StitchedPage(c.page, c.text) for c in doc.chunks], normalized_document=doc)
    record = DocumentRecord(record_id, doc.file_name, 0, b"", status="completed", page_count=doc.page_count, processed_document=processed)
    record.pages = service.store._build_pages(processed)
    record.report = DocumentReport(document_id=record_id, file_name=doc.file_name, page_count=doc.page_count, processing_seconds=0, summary=DocumentSummary())
    record.retrieval_index = build_index(doc, vectors={c.chunk_id: [1.0, 0.0] for c in doc.chunks}) if semantic else build_index(doc)
    service.store._documents[record_id] = record
    service.store._persist_artifacts(record)
    return record_id


def test_valid_restart_restores_semantic_index_without_embedding_calls(tmp_path):
    calls = []
    first = make_service(tmp_path, lambda: Worker(calls))
    record_id = install_record(first)
    first.shutdown()

    restarted_calls = []
    restarted = make_service(tmp_path, lambda: Worker(restarted_calls))
    record = restarted.store.get(record_id)
    assert record.retrieval_index is not None and record.retrieval_index._vectors
    assert restarted_calls == []
    restarted.shutdown()


def test_mismatch_and_corrupt_vectors_retain_canonical_lexical_index(tmp_path):
    cases = ("document_sha256", "model", "dimension", "text_hashes", "normalized_document")
    for field in cases:
        root = tmp_path / field
        root.mkdir()
        service = make_service(root, lambda: Worker([], failure=True))
        record_id = install_record(service)
        path = root / "documents" / record_id / "semantic_index.v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if field == "normalized_document":
            payload[field]["citations"]["P1-D1"]["excerpt"] = "wrong citation"
        elif field == "text_hashes":
            payload[field]["P1-D1"] = "wrong hash"
        elif field == "dimension":
            payload[field] = 99
        elif field == "model":
            payload[field] = "wrong-model"
        else:
            payload[field] = "wrong-sha"
        path.write_text(json.dumps(payload), encoding="utf-8")
        service.store._documents.pop(record_id, None)
        record = service.store.get(record_id)
        assert record.retrieval_index is not None and not record.retrieval_index._vectors
        service.shutdown()

    root = tmp_path / "vectors"
    root.mkdir()
    service = make_service(root, lambda: Worker([], failure=True))
    record_id = install_record(service)
    path = root / "documents" / record_id / "semantic_index.v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["vectors"]["P1-D1"] = ["bad"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    service.store._documents.pop(record_id, None)
    record = service.store.get(record_id)
    assert record.retrieval_index is not None and not record.retrieval_index._vectors
    service.shutdown()


def test_rebuild_singleflight_and_atomic_success_or_failure_retention(tmp_path):
    calls = []
    started = threading.Event()
    service = make_service(tmp_path, lambda: Worker(calls, started=started))
    record_id = install_record(service, semantic=False)
    record = service.store._documents[record_id]
    record.semantic_rebuild_needed = True
    threads = [threading.Thread(target=service.store._schedule_rebuild, args=(record,)) for _ in range(8)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert started.wait(2)
    deadline = time.time() + 5
    while not record.retrieval_index._vectors and time.time() < deadline:
        time.sleep(0.01)
    assert calls == [4] and record.retrieval_index._vectors
    service.shutdown()

    failed_calls = []
    failed = make_service(tmp_path / "failed", lambda: Worker(failed_calls, failure=True))
    failed_id = install_record(failed, semantic=False)
    failed_record = failed.store._documents[failed_id]
    failed_record.semantic_rebuild_needed = True
    failed.store._schedule_rebuild(failed_record)
    failed_record.semantic_rebuild_future.result(timeout=5)
    assert not failed_record.retrieval_index._vectors
    failed.shutdown()


def test_repeated_qa_embeds_queries_only_and_factory_is_loop_local(tmp_path):
    worker_ids = []
    worker_calls = []

    def factory():
        worker = Worker(worker_calls)
        worker_ids.append(id(worker))
        return worker

    class QueryClient:
        async def embed(self, texts):
            self.calls += 1
            return [[1.0, 0.0]]
        async def call(self, messages, response_model):
            raise RuntimeError("not used")
        def __init__(self): self.calls = 0

    query = QueryClient()
    service = make_service(tmp_path, factory, query)
    record_id = install_record(service)
    record = service.store._documents[record_id]
    asyncio.run(service.answer_question(record_id, "kinh phí ngân sách"))
    asyncio.run(service.answer_question(record_id, "kinh phí ngân sách"))
    assert query.calls == 2
    assert worker_calls == []

    async def build_once():
        await service.store._build_semantic_index(document())
    asyncio.run(build_once())
    asyncio.run(build_once())
    assert len(set(worker_ids)) >= 2
    service.shutdown()
