# API Contract v1 — Antipaper

## 1. Context

Base path: `/api/v1`  
Media type: `application/json`, trừ upload `multipart/form-data`  
Pagination hiện tại: `limit`/`offset`  
Page number: số nguyên 1-based

Contract này mô tả API đã có và bổ sung yêu cầu target tương thích. Field target chưa
triển khai được đánh dấu **Target**. OpenAPI do FastAPI sinh là executable schema; CI
phải kiểm tra nó không drift khỏi tài liệu này.

## 2. Problem Statement

Frontend và backend hiện chia sẻ type bằng cách khai báo thủ công, nên có nguy cơ lệch
stage/citation fields. Mặt khác `X-User-ID` chỉ là định danh demo, không phải cơ chế
authentication. Contract phải ổn định cho hackathon nhưng công khai các giới hạn trước
khi tích hợp pilot.

## 3. Technical Deep-Dive

### 3.1 Quy ước chung

#### Headers

| Header | MVP hiện tại | Pilot target |
|---|---|---|
| `Content-Type` | JSON hoặc multipart | Giữ nguyên |
| `X-User-ID` | Chuỗi client tự tạo; default `demo-user` | Loại bỏ khỏi trust decision |
| `Authorization` | Chưa có | `Bearer <OIDC access token>` |
| `X-Request-ID` | Chưa có | Optional từ client, server luôn trả correlation ID |
| `Idempotency-Key` | Chưa có | Bắt buộc/khuyến nghị cho upload retry |

Mọi document endpoint ở pilot phải authorize theo tenant/workspace/owner; biết UUID
không đồng nghĩa có quyền truy cập.

#### Error envelope

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document is no longer active. Upload it again to open its report.",
    "retryable": false
  }
}
```

Không đưa stack trace, file content, provider response hoặc credential vào `message`.

#### Status

`DocumentStatus = queued | processing | completed | failed`

Stage canonical target:

```text
queued | extracting | normalizing | indexing | generating |
validating | ready | answering | failed
```

MVP thực tế dùng `queued | parsing | generating | ready | failed`; client hiện còn
khai báo một số stage chưa được backend phát. Field `stage` là extensible string, UI
phải có fallback label.

### 3.2 Endpoint catalog

| Method | Path | Mục đích | Auth MVP | Thành công |
|---|---|---|---|---|
| GET | `/health` | Health/version/mode | Không | 200 |
| POST | `/documents` | Upload và tạo task | `X-User-ID` | 202 |
| GET | `/documents/{id}/status` | Poll trạng thái | Không owner-check | 200 |
| GET | `/documents/{id}/report` | Lấy report | Không owner-check | 200 |
| GET | `/documents/{id}/pages/{page}` | Xem nguồn | Không owner-check | 200 |
| POST | `/documents/{id}/questions` | Hỏi đáp | `X-User-ID` | 200 |
| GET | `/history` | Danh sách task | `X-User-ID` | 200 |
| GET | `/history/{task_id}` | Chi tiết task | `X-User-ID` | 200 |
| DELETE | `/history/{task_id}` | Xóa task history chưa gắn document | `X-User-ID` | 204 |
| DELETE | `/history/sessions/{document_id}` | Xóa toàn bộ history của một phiên | `X-User-ID` | 204 |

Thiếu owner-check là gap P0 trước pilot, không phải hành vi được khuyến nghị.

### 3.3 Health

#### `GET /api/v1/health`

Response hiện tại:

```json
{
  "status": "ok",
  "service": "antipaper-backend",
  "version": "0.1.0",
  "llm_status": "enabled"
}
```

**Target:** tách liveness và readiness; không trả `ready` nếu queue/DB bắt buộc không
khả dụng. `llm_status` phải phản ánh provider/config thực sự dùng, không hard-code.

### 3.4 Upload

#### `POST /api/v1/documents`

Request:

```http
Content-Type: multipart/form-data
X-User-ID: web-<uuid>

file=<PDF or DOCX bytes>
```

Constraints hiện tại:

- extension `.pdf` hoặc `.docx`;
- tối đa 25 MiB;
- một file/request;
- cùng bytes vẫn tạo document/task mới.

Response `202 Accepted`:

```json
{
  "document_id": "7d14b988-4e44-4f6a-9465-770e159d45b9",
  "status": "queued",
  "task_id": "22fc6140-39e8-493e-82bd-6296e1e9742f"
}
```

Không suy luận report đã sẵn sàng từ HTTP 202. **Target:** hỗ trợ
`Idempotency-Key` để network retry không nhân đôi task ngoài ý muốn; điều này khác với
việc cố ý upload lại file giống nhau.

### 3.5 Status

#### `GET /api/v1/documents/{document_id}/status`

```json
{
  "document_id": "7d14b988-4e44-4f6a-9465-770e159d45b9",
  "status": "processing",
  "stage": "parsing",
  "progress": 15,
  "elapsed_seconds": 1.284,
  "error": null
}
```

Rules:

- `progress` trong `[0,100]`, dùng cho UX chứ không phải SLA guarantee.
- Terminal `failed` có `error`; terminal `completed` không có error.
- Client poll khoảng 2 giây, dừng tại terminal; production dùng exponential backoff/
  jitter hoặc server events nếu cần.

### 3.6 Report

#### `GET /api/v1/documents/{document_id}/report`

Precondition: document completed. MVP implementation có thể block chờ future tới
deadline; target nên trả `409 REPORT_NOT_READY` thay vì giữ GET lâu.

Schema rút gọn:

```json
{
  "document_id": "uuid",
  "file_name": "tai-lieu.pdf",
  "page_count": 44,
  "processing_seconds": 8.231,
  "summary": {
    "context": [
      {"text": "…", "citation_ids": ["P1-D1"]}
    ],
    "main_content": [],
    "decision_points": [],
    "impact": []
  },
  "terms": [
    {
      "term": "an ninh mạng",
      "explanation": "…",
      "citation_ids": ["P2-D1"]
    }
  ],
  "suggested_questions": [
    {
      "question": "…?",
      "rationale": "…",
      "citation_ids": ["P10-D1"]
    }
  ],
  "related_documents": [],
  "citations": {
    "P1-D1": {
      "page": 1,
      "chapter": null,
      "article": null,
      "clause": null,
      "excerpt": "…"
    }
  },
  "generation_mode": "llm",
  "quality": {
    "pipeline": "llm_map_reduce",
    "map_batch_count": 4,
    "question_count": 5,
    "summary_sections_complete": true,
    "citations_valid": true,
    "citation_count": 44
  },
  "enrichment_status": "not_configured"
}
```

Rules:

- Report phát hành luôn có `generation_mode = llm`; lỗi cấu hình/model/schema/citation trả document task trạng thái `failed`, không trả heuristic fallback.
- `enrichment_status = not_configured | pending | completed | failed`.
- Các `citation_ids` phải là key trong `citations`.
- Terms tối đa 100 theo schema hiện tại.
- `quality` mở rộng tương thích ngược với `pipeline`, `map_batch_count`, `question_count`, `summary_sections_complete` và `citations_valid`.
- `processing_seconds` đo core report, không mặc nhiên bao gồm enrichment nền.

### 3.7 Page source

#### `GET /api/v1/documents/{document_id}/pages/{page_number}`

```json
{
  "document_id": "uuid",
  "page_number": 12,
  "text": "Nội dung trang…",
  "blocks": [
    {"kind": "text", "text": "Nội dung trang…", "page_number": 12}
  ],
  "source_preview": {
    "kind": "page_image",
    "mime_type": "image/png",
    "data_url": "data:image/png;base64,…",
    "width": 714,
    "height": 1010,
    "page_number": 12
  }
}
```

MVP chỉ render preview cho PDF. **Target:** trả binary image endpoint hoặc signed URL
thay cho data URL; cache private; kiểm authorization trên mỗi request.

### 3.8 Questions

#### `POST /api/v1/documents/{document_id}/questions`

Request:

```json
{"question": "Điều 40 giao trách nhiệm cho cơ quan nào?"}
```

Question dài 1–4.000 ký tự.

Response có evidence:

```json
{
  "answer": "…",
  "insufficient_evidence": false,
  "citation_ids": ["P39-D1"],
  "latency_ms": 12.4,
  "task_id": "uuid"
}
```

Response từ chối:

```json
{
  "answer": "Không đủ thông tin trong tài liệu để trả lời.",
  "insufficient_evidence": true,
  "citation_ids": [],
  "latency_ms": 1.8,
  "task_id": "uuid"
}
```

Invariant: `insufficient_evidence=true` kéo theo `citation_ids=[]`. Client không được
gắn citation từ lượt trước hoặc từ retrieval debug.

### 3.9 History

#### `GET /api/v1/history`

Query:

| Field | Type | Default | Constraint |
|---|---|---:|---|
| `limit` | integer | 20 | 1–100 |
| `offset` | integer | 0 | ≥0 |
| `status` | enum | — | document status |
| `task_type` | enum | — | `document_processing`/`question_answer` |
| `from_at` | datetime | — | ISO 8601 |
| `to_at` | datetime | — | ISO 8601 |

Response:

```json
{
  "items": [
    {
      "task_id": "uuid",
      "task_type": "document_processing",
      "document_id": "uuid",
      "display_name": "tai-lieu.pdf",
      "status": "completed",
      "stage": "ready",
      "progress": 100,
      "created_at": "2026-07-19T01:00:00Z",
      "started_at": "2026-07-19T01:00:00Z",
      "updated_at": "2026-07-19T01:00:08Z",
      "completed_at": "2026-07-19T01:00:08Z",
      "duration_seconds": 8.2,
      "error": null
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

History metadata còn sau restart không bảo đảm report còn active.

#### `GET /api/v1/history/{task_id}`

Trả một `TaskHistoryItem`; MVP query đã scope theo `X-User-ID`.

#### `DELETE /api/v1/history/sessions/{document_id}`

Xóa vĩnh viễn toàn bộ `TaskHistoryItem` có cùng `document_id`, được scope theo
`X-User-ID`; trả `204 No Content`. Endpoint không xóa document/report đang active trong
bộ nhớ. Nếu phiên không tồn tại hoặc không thuộc user, trả `404 HISTORY_NOT_FOUND`.

#### `DELETE /api/v1/history/{task_id}`

Xóa một task history độc lập chưa có `document_id`, được scope theo `X-User-ID`; trả
`204 No Content`. UI dùng endpoint này cho task upload thất bại trước khi tạo document.

### 3.10 Error matrix

| HTTP | Code | Khi nào | Retryable |
|---:|---|---|---:|
| 400/422 | `VALIDATION_ERROR` | Request/header/body sai | Không |
| 401 | `UNAUTHENTICATED` | Target: token thiếu/hết hạn | Sau đăng nhập |
| 403 | `FORBIDDEN` | Target: không có quyền | Không |
| 404 | `DOCUMENT_NOT_FOUND` | ID không active/không tồn tại | Không; upload lại |
| 404 | `HISTORY_NOT_FOUND` | Task không thuộc user/không tồn tại | Không |
| 409 | `PROCESSING_FAILED` | Report/page chưa có hoặc task lỗi | Tùy payload |
| 409 | `QUALITY_GATE_FAILED` | Target: output không đạt | Không tự động |
| 413 | `FILE_TOO_LARGE` | >25 MiB | Không |
| 415 | `UNSUPPORTED_FILE` | Không phải PDF/DOCX | Không |
| 504 | `MODEL_TIMEOUT` | Chờ processing quá deadline | Có |
| 429 | `RATE_LIMITED` | Target: quota/concurrency | Có, kèm Retry-After |

### 3.11 Compatibility policy

- Thêm nullable field hoặc enum value mới: backward compatible; client phải ignore field
  lạ và fallback enum lạ.
- Xóa/đổi nghĩa field, đổi type, biến optional thành required: breaking; dùng `/api/v2`.
- Error `code` là machine-readable và ổn định; `message` có thể đổi/localize.
- OpenAPI snapshot và generated frontend client là CI gate.

## 4. Strategic Recommendations

1. Ưu tiên owner authorization cho mọi endpoint trước mọi feature pilot.
2. Chuẩn hóa state/stage và quality schema; loại các string union trùng nhưng lệch giữa
   Python và TypeScript.
3. Bổ sung `section`/`point` vào public citation schema và test compatibility.
4. Chuyển page preview khỏi base64 JSON khi triển khai lâu dài.
5. Thêm request ID, idempotency, rate limit, `Retry-After` và audit correlation.
