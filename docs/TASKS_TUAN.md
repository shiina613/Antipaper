# Công việc — Tuấn

## Vai trò

Phụ trách luồng nhập/chuẩn hóa tài liệu và LLM client dùng chung. Đầu ra là nền tảng citation và adapter model cho cả đội.

**Nhánh:** `feat/tuan-document-pipeline`
**Khối lượng dự kiến:** 24 giờ công tập trung
**Người duyệt chính:** Hưng

## Công việc

| ID | Việc | Giờ | Hạn | Điều kiện hoàn thành |
|---|---|---:|---|---|
| TUAN-01 | Chốt `NormalizedDocument`, `Page`, `Chunk`, `Citation` với Hưng và xuất normalized fixture tối thiểu | 3 | H4 | Pydantic models và JSON mẫu khớp `API_CONTRACT.md`; thay được mock của Hậu mà không đổi consumer |
| TUAN-05 | LLM client dùng chung: config, timeout, retry và schema validation | 4 | H8 | Model cấu hình qua env; lỗi/timeout chuẩn; inject được vào intelligence implementation của Hậu |
| TUAN-02 | Tạo fast path PDF/text/bảng native bằng PyMuPDF | 6 | H14 | Đủ số trang; `find_tables()` xuất Markdown; YOLO không chạy mặc định |
| TUAN-04 | Parse Chương/Mục/Điều/Khoản và tạo chunk/citation ID | 6 | H20 | Citation map ngược đúng nguồn; có normalized JSON của tài liệu demo |
| TUAN-03 | Thêm DOCX loader và validation MIME/kích thước | 5 | H25 | PDF/DOCX trả cùng schema; file lỗi có exception chuẩn |

## Giao diện bàn giao

```python
def ingest_document(path: Path) -> NormalizedDocument: ...
async def call_llm(messages: list[dict], response_model: type[T]) -> T: ...
```

Module ingestion không gọi LLM và phải deterministic. LLM client nằm ở module riêng, không chứa prompt nghiệp vụ.

## Phụ thuộc

- Dùng `IntelligenceReport`, mock JSON và quy tắc citation do Hậu chốt tại H3; không yêu cầu Hậu chờ model ingestion hoàn chỉnh.
- Chốt model Pydantic với Hưng tại H4 và bàn giao normalized fixture tối thiểu cho Hậu/Tùng Anh ngay tại mốc này.
- Chốt cấu hình model, timeout và error contract với Hậu/Hưng, rồi bàn giao client inject được tại H8.
- `TUAN-02` chạy trong H8–H14: phần fast path native không phụ thuộc OCR; OCR adapter Hậu đã bàn giao tại H7 chỉ được nối vào nhánh fallback khi native extraction không đạt ngưỡng.
- Thông báo trước khi thay đổi `chunk_id` hoặc metadata citation.

## Ngoài phạm vi

- Không huấn luyện table detector.
- Không triển khai OCR; Hậu sở hữu OCR adapter, Tuấn chỉ tích hợp router theo trang.
- Không tự xây API hoặc UI.

## Checklist bàn giao

- [ ] Tài liệu demo đủ số trang gốc và có page number đúng.
- [ ] Parser nhận diện được Điều/Khoản phổ biến.
- [ ] DOCX smoke test hoạt động.
- [ ] Không cần YOLO weights ở luồng mặc định.
- [ ] LLM client dùng chung xử lý timeout/retry/schema error.
- [ ] Test và sample JSON được commit.
