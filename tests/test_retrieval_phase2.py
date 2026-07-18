from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from intelligence import NormalizedDocument
from retrieval import RetrievalIndex, answer, build_index, build_index_async


ROOT = Path(__file__).parents[1]


def document() -> NormalizedDocument:
    payload = json.loads((ROOT / "docs/fixtures/normalized_document.mock.json").read_text(encoding="utf-8"))
    return NormalizedDocument.model_validate(payload)


def test_async_builder_batches_once_and_uses_keyed_vectors():
    calls = 0

    async def embed(texts):
        nonlocal calls
        calls += 1
        return [[float(index + 1), 0.0] for index, _ in enumerate(texts)]

    index = asyncio.run(build_index_async(document(), embed))
    assert calls == 1
    assert index.search("kinh phí ngân sách")


def test_async_builder_batches_documents_over_default_batch_size():
    source_payload = {
        "document_id": "large", "file_name": "large.pdf", "page_count": 65,
        "chunks": [{"chunk_id": f"C{i}", "page": i + 1, "text": f"Nội dung pháp lý {i}"} for i in range(65)],
        "citations": {},
    }
    source = NormalizedDocument.model_validate(source_payload)
    calls: list[int] = []

    async def embed(texts):
        calls.append(len(texts))
        return [[1.0, 0.0] for _ in texts]

    asyncio.run(build_index_async(source, embed))
    assert calls == [64, 1]


def test_keyed_vectors_reject_missing_and_extra_ids():
    source = document()
    vectors = {chunk.chunk_id: [1.0] for chunk in source.chunks}
    missing = dict(vectors)
    missing.pop("P1-D1")
    with pytest.raises(ValueError):
        build_index(source, vectors=missing)
    extra = dict(vectors, EXTRA=[1.0])
    with pytest.raises(ValueError):
        build_index(source, vectors=extra)


def test_explicit_keyed_vectors_reject_bool_nan_and_inconsistent_dimensions():
    source = document()
    base = {chunk.chunk_id: [1.0, 0.0] for chunk in source.chunks}
    for bad in (
        {**base, "P1-D1": [True, 0.0]},
        {**base, "P1-D1": [float("nan"), 0.0]},
        {**base, "P1-D1": [1.0]},
        {**base, "P1-D1": []},
    ):
        with pytest.raises(ValueError):
            build_index(source, vectors=bad)


def test_legacy_sync_embedding_precomputes_chunks_once():
    source = document()
    chunk_calls = 0

    def embed(text):
        nonlocal chunk_calls
        if any(text == chunk.text for chunk in source.chunks):
            chunk_calls += 1
        return [1.0, 0.0]

    index = build_index(source, embedding=embed)
    assert chunk_calls == len(source.chunks)
    index.search("kinh phí")
    index.search("ngân sách")
    assert chunk_calls == len(source.chunks)


def test_malformed_legacy_vectors_fall_back_to_lexical():
    source = document()
    malformed = ([True, 0.0], [float("nan"), 0.0], [], [1.0])
    for vector in malformed:
        index = build_index(source, embedding=lambda _text, vector=vector: vector)
        assert index.search("kinh phí ngân sách", top_k=1)[0].chunk_id == "P3-D2"


def test_precomputed_vectors_never_reembed_and_query_runs_once():
    source = document()
    vectors = {chunk.chunk_id: ([1.0, 0.0] if chunk.chunk_id == "P8-D4" else [0.0, 1.0]) for chunk in source.chunks}
    index = build_index(source, vectors=vectors)
    calls = 0

    async def query(texts):
        nonlocal calls
        calls += 1
        return [[1.0, 0.0]]

    assert index.search("đầu mối")
    result = asyncio.run(index.asearch("semantic target", query, top_k=1))
    assert calls == 1
    assert result[0].chunk_id == "P8-D4"


def test_query_failure_dimension_and_nan_fall_back_to_lexical():
    source = document()
    vectors = {chunk.chunk_id: [1.0, 0.0] for chunk in source.chunks}
    index = build_index(source, vectors=vectors)

    async def broken(_texts):
        raise RuntimeError("embedding unavailable")

    assert asyncio.run(index.asearch("kinh phí ngân sách", broken, 1))[0].chunk_id == "P3-D2"

    async def bad_dimension(_texts):
        return [[1.0, 0.0, 0.0]]

    assert asyncio.run(index.asearch("kinh phí ngân sách", bad_dimension, 1))[0].chunk_id == "P3-D2"

    async def bad_nan(_texts):
        return [[float("nan"), 0.0]]

    assert asyncio.run(index.asearch("kinh phí ngân sách", bad_nan, 1))[0].chunk_id == "P3-D2"


def test_query_embedder_requires_exact_one_vector_list_shape():
    source = document()
    vectors = {chunk.chunk_id: [1.0, 0.0] for chunk in source.chunks}
    index = build_index(source, vectors=vectors)
    bad_values = [
        [1.0, 0.0],
        [[1.0, 0.0], [0.0, 1.0]],
        [[True, 0.0]],
        [[float("nan"), 0.0]],
        [[1.0, 0.0, 0.0]],
    ]
    for value in bad_values:
        async def embed(_texts, value=value):
            return value
        assert asyncio.run(index.asearch("kinh phí ngân sách", embed, 1))[0].chunk_id == "P3-D2"


def test_lexical_exact_hit_is_reserved_against_adverse_semantic_vector():
    source = document()
    vectors = {chunk.chunk_id: ([1.0, 0.0] if chunk.chunk_id == "P1-D1" else [0.0, 1.0]) for chunk in source.chunks}
    index = build_index(source, vectors=vectors)

    async def adverse(_texts):
        return [[1.0, 0.0]]

    result = asyncio.run(index.asearch("kinh phí ngân sách", adverse, top_k=2))
    assert result[0].chunk_id == "P3-D2"


def test_lexical_reservation_uses_meaningful_tokens_and_threshold():
    source = document()
    vectors = {chunk.chunk_id: ([1.0, 0.0] if chunk.chunk_id == "P1-D1" else [0.0, 1.0]) for chunk in source.chunks}
    index = build_index(source, vectors=vectors, lexical_reservation_threshold=0.75)

    async def adverse(_texts):
        return [[1.0, 0.0]]

    result = asyncio.run(index.asearch("Kinh phí lấy từ đâu?", adverse, top_k=2))
    assert result[0].chunk_id == "P3-D2"


def test_lexical_reservation_threshold_above_coverage_allows_semantic_first():
    source = document()
    vectors = {chunk.chunk_id: ([1.0, 0.0] if chunk.chunk_id == "P1-D1" else [0.0, 1.0]) for chunk in source.chunks}
    index = build_index(source, vectors=vectors, lexical_reservation_threshold=0.8)

    async def adverse(_texts):
        return [[1.0, 0.0]]

    # P3-D2 matches 4/6 meaningful terms (below reservation threshold).
    result = asyncio.run(index.asearch("kinh phí ngân sách foobar baz", adverse, top_k=2))
    assert result[0].chunk_id == "P1-D1"


def test_negative_reservation_threshold_is_rejected():
    with pytest.raises(ValueError):
        build_index(document(), lexical_reservation_threshold=-0.1)


def test_more_than_fifty_positive_semantic_candidates_are_capped():
    payload = {
        "document_id": "semantic-large", "file_name": "large.pdf", "page_count": 60,
        "chunks": [{"chunk_id": f"S{i}", "page": i + 1, "text": f"unique text {i}"} for i in range(60)],
        "citations": {},
    }
    source = NormalizedDocument.model_validate(payload)
    vectors = {chunk.chunk_id: [1.0, 0.0] for chunk in source.chunks}
    index = build_index(source, vectors=vectors)

    async def query(_texts):
        return [[1.0, 0.0]]

    results = asyncio.run(index.asearch("unrelated", query, top_k=60))
    assert len(results) == 50


def test_index_deep_copies_document_chunks_and_citations():
    source = document()
    index = build_index(source)
    original_text = index.chunks[0].text
    source.chunks[0].text = "mutated upstream text"
    source.citations["P1-D1"].excerpt = "mutated citation"
    assert index.chunks[0].text == original_text
    assert index.document.citations["P1-D1"].excerpt != "mutated citation"


def test_public_answer_wrapper_accepts_query_embedder():
    source = document()
    vectors = {chunk.chunk_id: ([1.0, 0.0] if chunk.chunk_id == "P8-D4" else [0.0, 1.0]) for chunk in source.chunks}
    index = build_index(source, vectors=vectors)
    calls = 0

    async def query(_texts):
        nonlocal calls
        calls += 1
        return [[1.0, 0.0]]

    result = asyncio.run(answer(index, "đầu mối phối hợp", query_embedder=query))
    assert calls == 1
    assert result.citation_ids
