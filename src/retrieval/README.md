# Retrieval (TA-01/02/03/05)

## Kiến trúc

`src/retrieval` là lớp in-memory, pure Python, deterministic:

- **TA-01**: BM25 lexical; embedding callable tùy chọn với cosine và RRF hybrid. Không có vector database hay dependency model.
- **TA-02**: `GroundedQAService` truy hồi context, trả lời extractive mặc định; LLM chỉ được truyền vào qua callable.
- **TA-03**: validator/renderer citation fail-closed, kiểm tra ID, retrieval scope, metadata và excerpt nguồn.
- **TA-05**: golden evaluator đo Recall@5, citation precision, groundedness, OOS accuracy và latency.

## Input contract

API nhận `intelligence.contracts.NormalizedDocument`, gồm `chunks: list[DocumentChunk]` và citation metadata tùy chọn. Mỗi chunk cần `chunk_id`, `page`, `text`; `chunk_id` là ID upstream, retrieval không tạo ID mới.

## Public API

```python
from retrieval import (
    GroundedQAService,
    build_index,
    validate_citations,
    render_citations,
)

index = build_index(document, embedding=None)
results = index.search("Kinh phí lấy từ đâu?", top_k=5)
answer = await GroundedQAService(index).answer("Kinh phí lấy từ đâu?")

check = validate_citations(
    answer.citation_ids,
    document,
    answer.retrieved_ids,
)
rendered = render_citations(check)
```

Semantic vectors can be precomputed without network activity in constructors:

```python
index = build_index(document, vectors={chunk.chunk_id: vector for chunk, vector in ...})
index = await build_index_async(document, async_batch_embedder)
results = await index.asearch("question", async_query_embedder, top_k=5)
```

`build_index_async` calls document embedding once in batch. Query embedding is
called once per `asearch`; failures fall back to lexical retrieval without
mutating index vectors. `lexical_reservation_threshold` defaults to `0.5` and
reserves a positive-BM25 lexical top result when meaningful query-token
coverage reaches that threshold.

`RetrievalResult` giữ nguyên `chunk`, `chunk_id`, `metadata`, `score`, `lexical_score`, `semantic_score`.

`GroundedAnswer` cung cấp `answer`, `citations`, `citation_ids`, `confidence`, `out_of_scope`, `insufficient_evidence`, `latency_ms`; `to_dict()` trả payload serializable.

Citation hợp lệ phải là list ID không blank/duplicate/unknown, thuộc retrieved chunks, có metadata nhất quán và excerpt là substring đã normalize của chunk nguồn. LLM output không được chấp nhận nếu prose không được cited chunk hỗ trợ; hệ thống fallback extractive hoặc từ chối OOS.

## Golden evaluator

```python
from retrieval import evaluate_golden_set, load_golden_cases

cases = load_golden_cases("tests/fixtures/golden_retrieval.json")
report = evaluate_golden_set(index, cases)
print(report.as_dict())
```

Async code dùng `evaluate_golden_set_async`. Case in-scope được chấm retrieval/citation/groundedness; OOS được chấm riêng bằng `oos_accuracy`.

## Tests

```powershell
python -m pytest tests/test_retrieval.py tests/test_citations.py tests/test_golden_retrieval.py -q
```

## GPT-4o mini tùy chọn

Backend dùng shared `LlmClient` khi có `OPENAI_API_KEY` (ưu tiên) hoặc
`LLM_API_KEY`; model mặc định `gpt-4o-mini`. Endpoint mặc định là
`https://api.openai.com/v1/chat/completions`, có thể ghi đè bằng
`LLM_API_URL` hoặc `LLM_BASE_URL`. Không commit key. Thiếu cấu hình, lỗi API,
timeout hoặc schema đều fallback về extractive answer/OOS.

## Giới hạn và ownership

- Phụ thuộc upstream cung cấp `NormalizedDocument` và normalized chunks hợp lệ.
- Không tạo client LLM/embedding, không gọi network.
- Đã tích hợp Streamlit và FastAPI report/Q&A.
- TA-04: `related.py` + catalog cục bộ `docs/fixtures/related_documents_catalog.json`.
