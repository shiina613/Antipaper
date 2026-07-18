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

## Giới hạn và ownership

- Phụ thuộc upstream cung cấp `NormalizedDocument` và normalized chunks hợp lệ.
- Không tạo client LLM/embedding, không gọi network.
- Đã tích hợp Streamlit và FastAPI report/Q&A.
- TA-04: `related.py` + catalog cục bộ `docs/fixtures/related_documents_catalog.json`.
