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
| TA-04 | Trích căn cứ pháp lý và đối chiếu catalog JSON | 6 | H24 | Related docs có tên/số hiệu/lý do/citation; không bịa văn bản |
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

- [ ] Retrieval có embedding và lexical fallback.
- [ ] Citation precision mục tiêu ≥90% trên golden set.
- [ ] 3/3 câu ngoài phạm vi bị từ chối.
- [ ] Related docs đều có nguồn kiểm chứng.
- [ ] API consumer nhận đúng schema đã chốt.
