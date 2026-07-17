# Công việc — Hưng

## Vai trò

Phụ trách nền chạy backend, API, điều phối, cache, đo hiệu năng và đóng gói demo.

**Nhánh:** `feat/hung-backend-runtime`
**Khối lượng dự kiến:** 24 giờ công tập trung
**Người duyệt chính:** Tuấn

## Công việc

| ID | Việc | Giờ | Hạn | Điều kiện hoàn thành |
|---|---|---:|---|---|
| HUNG-01 | FastAPI skeleton, CORS, models và error format | 4 | H8 | Endpoints đúng `API_CONTRACT.md`; OpenAPI chạy được |
| HUNG-02 | Upload, job status, in-memory store và cache SHA-256 | 6 | H16 | Request không block; polling hoạt động; cache hit rõ ràng |
| HUNG-03 | Orchestrate ingestion, intelligence, retrieval và report | 4 | H24 | Một API flow hoàn chỉnh chạy trên `$DEMO_DOCUMENT_PATH` |
| HUNG-04 | Benchmark từng stage và tối ưu concurrency/timeout | 6 | H32 | Có cold + 3 warm runs; ít nhất một run hợp lệ dưới 60 giây |
| HUNG-05 | Health, log an toàn, script run và đóng gói deploy | 4 | H38 | Team chạy backend bằng một lệnh; không log key/toàn văn |

## API bắt buộc

- `POST /api/v1/documents`
- `GET /api/v1/documents/{id}/status`
- `GET /api/v1/documents/{id}/report`
- `POST /api/v1/documents/{id}/questions`
- `GET /api/v1/documents/{id}/pages/{page}`

## Phụ thuộc

- Chốt Pydantic models với Tuấn tại H2.
- Cấp mock endpoints cho Tùng từ H8.
- Tích hợp output Hậu và Tùng Anh theo schema, không sửa field âm thầm.

## Ngoài phạm vi

- Không thêm Redis/Celery/database nếu in-memory đáp ứng demo.
- Không triển khai auth production.
- Không tính cache hit là benchmark chính.

## Checklist bàn giao

- [ ] API contract không bị phá vỡ.
- [ ] Job failed/timeout trả lỗi rõ.
- [ ] Cache theo content hash hoạt động.
- [ ] Benchmark có cấu hình máy và commit.
- [ ] Backend khởi động bằng một lệnh.
