# Công việc — Hưng

## Vai trò

Phụ trách nền chạy backend, API, điều phối, cache, xử lý bottleneck runtime và đóng gói backend.

**Nhánh:** `feat/hung-backend-runtime`
**Khối lượng dự kiến:** 18 giờ công tập trung
**Người duyệt chính:** Tuấn

## Công việc

| ID | Việc | Giờ | Hạn | Điều kiện hoàn thành |
|---|---|---:|---|---|
| [x] HUNG-01 | FastAPI skeleton, CORS, models và error format | 4 | H8 | Endpoints đúng `API_CONTRACT.md`; OpenAPI chạy được |
| [x] HUNG-02 | Upload, job status, in-memory store và cache SHA-256 | 6 | H16 | Request không block; polling hoạt động; cache hit rõ ràng |
| [x] HUNG-03 | Orchestrate ingestion, intelligence, retrieval và report | 4 | H24 | Một API flow hoàn chỉnh chạy trên `$DEMO_DOCUMENT_PATH` |
| [x] HUNG-05 | Health, log an toàn, script run và đóng gói deploy | 4 | H38 | Team chạy backend bằng một lệnh; không log key/toàn văn |

> `HUNG-04` (6 giờ) được chuyển sang `TUNG-06` để cân bằng tải. Tùng sở hữu benchmark và bằng chứng nghiệm thu; Hùng chịu trách nhiệm sửa các bottleneck backend được phát hiện.

## API bắt buộc

- `POST /api/v1/documents`
- `GET /api/v1/documents/{id}/status`
- `GET /api/v1/documents/{id}/report`
- `POST /api/v1/documents/{id}/questions`
- `GET /api/v1/documents/{id}/pages/{page}`

## Phụ thuộc

- Nhận report schema/mock từ Hậu tại H3; chốt document Pydantic models với Tuấn tại H4.
- Cấp mock endpoints cho Tùng từ H8.
- Tích hợp output Hậu và Tùng Anh theo schema, không sửa field âm thầm.
- Hỗ trợ `TUNG-06` bằng stage timing và xử lý lỗi concurrency/timeout trước H32.

## Ngoài phạm vi

- Không thêm Redis/Celery/database nếu in-memory đáp ứng demo.
- Không triển khai auth production.
- Không tính cache hit là benchmark chính.

## Checklist bàn giao

- [x] API contract không bị phá vỡ.
- [x] Job failed/timeout trả lỗi rõ.
- [x] Cache theo content hash hoạt động.
- [x] Các bottleneck backend từ `TUNG-06` đã được xử lý hoặc ghi nhận rõ giới hạn.
- [x] Backend khởi động bằng một lệnh.
