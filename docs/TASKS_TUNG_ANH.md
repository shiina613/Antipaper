# Công việc — Tùng Anh

## Vai trò

Phụ trách truy hồi, Q&A bám nguồn, kiểm tra citation và gợi ý văn bản liên quan.

**Nhánh:** `feat/tung-anh-grounded-retrieval`
**Khối lượng dự kiến:** 24 giờ công tập trung
**Người duyệt chính:** Hậu

## Công việc

| ID | Việc | Giờ | Hạn | Điều kiện hoàn thành |
|---|---|---:|---|---|
| TA-03 | Citation validator và renderer trang/mục/điều | 4 | H8 | Loại ID không tồn tại; map đúng excerpt và metadata nguồn; Hậu tích hợp được như lớp kiểm tra cuối |
| TA-01 | Tạo embedding/index in-memory và lexical fallback | 4 | H12 | Nhận chunks, trả top-k kèm score; không cần vector database |
| TA-02 | Q&A tiếng Việt dựa trên retrieved chunks | 6 | H18 | Trả answer + citation IDs; câu ngoài phạm vi bị từ chối |
| TA-04 | Trích căn cứ pháp lý và đối chiếu catalog JSON | 6 | H24 | Related docs có tên/số hiệu/lý do/citation; không bịa văn bản ✅ |
| TA-05 | Tạo golden set và chấm citation/groundedness | 4 | H32 | 10 câu có đáp án + 3 câu ngoài phạm vi; có báo cáo tỷ lệ đúng |

## Giao diện bàn giao

```python
def build_index(document: NormalizedDocument) -> RetrievalIndex: ...
async def answer(index: RetrievalIndex, question: str) -> GroundedAnswer: ...
def validate_citations(ids: list[str], document: NormalizedDocument) -> list[Citation]: ...
```

## Phụ thuộc

- Nhận report schema, citation rule và mock document từ Hậu tại H3; bắt đầu validator bằng mock này, không đợi ingestion thật.
- Thay mock bằng normalized fixture tối thiểu của Tuấn tại H4; thay fixture không được làm đổi interface validator.
- Thống nhất citation ID với Hậu tại H3 và bàn giao validator cho Hậu/Hưng tại H8.
- Bàn giao response Q&A và related-doc schema cho Hưng/Tùng trước H12.

## Ngoài phạm vi

- Không crawl web trong thời gian demo.
- Không triển khai Chroma/FAISS/Elasticsearch.
- Không đánh giá câu trả lời chỉ bằng cảm tính; phải dùng golden set.

## Checklist bàn giao

- [x] Retrieval có embedding và lexical fallback.
- [x] Citation precision mục tiêu ≥90% trên golden set.
- [x] 3/3 câu ngoài phạm vi bị từ chối.
- [x] Related docs đều có nguồn kiểm chứng.
- [x] API consumer nhận đúng schema đã chốt.

## Cập nhật triển khai

- `src/retrieval/index.py` cung cấp BM25 lexical, embedding callable tùy chọn, cosine và RRF hybrid.
- `src/retrieval/qa.py` cung cấp `GroundedQAService`, trả lời extractive mặc định, từ chối câu ngoài phạm vi và chỉ chấp nhận LLM output nếu được chunk đã retrieve hỗ trợ.
- `src/retrieval/citations.py` cung cấp validator/renderer fail-closed: loại blank, duplicate, unknown, citation không nằm trong retrieved scope, metadata/excerpt không nhất quán.
- `src/retrieval/golden.py` đo Recall@5, citation precision, groundedness, OOS accuracy và latency.
- Golden set hiện có `12` câu trong phạm vi và `3` câu ngoài phạm vi tại `tests/fixtures/golden_retrieval.json`.
- Streamlit `app.py` đã chuyển sang dùng `build_index(document)` và `GroundedQAService`.

## Kiểm tra hiện tại

```powershell
python -m pytest tests/test_retrieval.py tests/test_citations.py tests/test_golden_retrieval.py -q
```

Kết quả hiện tại: `18 passed` (retrieval) + `tests/test_related_documents.py`.

## Cập nhật TA-04

- `src/retrieval/related.py` trích số hiệu/tên văn bản từ chunks và đối chiếu `docs/fixtures/related_documents_catalog.json`.
- Không dùng LLM để bịa văn bản liên quan; chỉ trả mục được nhắc trong tài liệu (có thể enrich bằng catalog).
- Streamlit và backend report đã surface `related_documents`.
