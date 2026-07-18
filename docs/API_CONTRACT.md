# Hợp đồng API v1

**Base URL:** `/api/v1`
**Content-Type:** JSON, riêng upload dùng `multipart/form-data`.

Frontend có thể làm bằng mock ngay khi tài liệu này được chốt. Thay đổi field sau giờ 4 phải có đồng thuận của Hưng và Tùng.

## 1. Upload tài liệu

`POST /documents`

Form field: `file` — PDF hoặc DOCX, tối đa 25 MB.

Phản hồi `202`:

```json
{
  "document_id": "sha256-prefix",
  "status": "queued",
  "cached": false
}
```

## 2. Theo dõi xử lý

`GET /documents/{document_id}/status`

```json
{
  "document_id": "sha256-prefix",
  "status": "processing",
  "stage": "summarizing",
  "progress": 65,
  "elapsed_seconds": 21.4,
  "error": null
}
```

`status`: `queued | processing | completed | failed`.

`error` là `null` khi tác vụ bình thường; khi thất bại, field này dùng cùng cấu
trúc `{code, message, retryable}` như lỗi chuẩn ở mục 6 để frontend hiển thị và
quyết định có cho phép thử lại hay không.

## 3. Lấy báo cáo

`GET /documents/{document_id}/report`

```json
{
  "document_id": "sha256-prefix",
  "file_name": "<tên-file-gốc>",
  "page_count": 44,
  "processing_seconds": 38.2,
  "summary": {
    "context": [{"text": "<một ý tổng hợp>", "citation_ids": ["P1-D1", "P3-D4"]}],
    "main_content": [
      {"text": "<luận điểm hoặc chủ đề thứ nhất>", "citation_ids": ["P3-D4", "P8-D2"]},
      {"text": "<luận điểm hoặc chủ đề thứ hai>", "citation_ids": ["P12-D1"]}
    ],
    "decision_points": [{"text": "<một nội dung cần quyết định>", "citation_ids": ["P20-D12", "P21-D3"]}],
    "impact": [{"text": "<một tác động hoặc rủi ro>", "citation_ids": ["P30-D18", "P32-D1"]}]
  },
  "terms": [
    {
      "term": "hệ thống thông tin quan trọng về an ninh quốc gia",
      "explanation": "...",
      "citation_ids": ["P5-D3"]
    }
  ],
  "suggested_questions": [
    {
      "question": "...",
      "rationale": "...",
      "citation_ids": ["P12-D7"]
    }
  ],
  "related_documents": [
    {
      "title": "...",
      "document_number": "...",
      "mentioned_name": "...",
      "source": "tavily",
      "reason": "...",
      "citation_ids": ["P1-D2"],
      "url": "https://example.gov.vn/van-ban",
      "publisher": "example.gov.vn",
      "excerpt": "..."
    }
  ],
  "citations": {
    "P12-D7": {
      "page": 12,
      "chapter": "Chương II",
      "article": "Điều 7",
      "clause": null,
      "excerpt": "..."
    }
  }
}
```

## 4. Hỏi đáp

`POST /documents/{document_id}/questions`

```json
{"question": "Cơ quan nào chịu trách nhiệm thực hiện nội dung này?"}
```

Phản hồi:

```json
{
  "answer": "...",
  "insufficient_evidence": false,
  "citation_ids": ["P18-D10"],
  "latency_ms": 1450
}
```

Nếu thiếu nguồn: `answer` nêu rõ không tìm thấy bằng chứng, `insufficient_evidence=true`, `citation_ids=[]`.

## 5. Nội dung trang

`GET /documents/{document_id}/pages/{page_number}`

Trả text, block và `source_preview` optional để frontend mở đúng trang/vùng. Với PDF còn lưu file gốc, `source_preview` là ảnh PNG data URL của đúng trang, phục vụ kiểm chứng trực quan giữa excerpt và tài liệu thật; với DOCX hoặc artifact cũ thiếu file gốc, trường này có thể là `null`.

```json
{
  "document_id": "sha256...",
  "page_number": 12,
  "text": "...",
  "blocks": [{"kind": "text", "text": "...", "page_number": 12}],
  "source_preview": {
    "kind": "page_image",
    "mime_type": "image/png",
    "data_url": "data:image/png;base64,...",
    "width": 804,
    "height": 1137,
    "page_number": 12
  }
}
```

Mỗi item trong `summary` là một ý tổng hợp độc lập được frontend hiển thị thành
một gạch đầu dòng, không phải câu trích rời rạc. Tổng nội dung của bốn nhóm không
vượt quá 800 từ và phải bao phủ các phần/chủ đề có ý nghĩa của toàn tài liệu.
`citation_ids` của từng item chứa tối đa sáu đoạn nguồn trực tiếp đã được dùng;
frontend gom các nguồn này dưới nút “Nguồn tóm tắt” và tải bản xem trang gốc của
từng trang liên quan.

`related_documents` chỉ chứa căn cứ trích được từ tài liệu. Khi có
`TAVILY_API_KEY`, backend đối chiếu bằng Tavily Search và chỉ giữ URL thuộc miền
`.gov.vn` hoặc `vnexpress.net`; `citation_ids` vẫn luôn trỏ về nơi căn cứ được nhắc
trong tài liệu gốc. Nếu không có căn cứ, API trả mảng rỗng thay vì placeholder.

## 6. Lỗi chuẩn

```json
{
  "error": {
    "code": "UNSUPPORTED_FILE",
    "message": "Chỉ hỗ trợ PDF hoặc DOCX.",
    "retryable": false
  }
}
```

Mã tối thiểu: `UNSUPPORTED_FILE`, `FILE_TOO_LARGE`, `DOCUMENT_NOT_FOUND`, `PROCESSING_FAILED`, `MODEL_TIMEOUT`, `INVALID_OUTPUT`.

## 7. Quy tắc tương thích

- Không đổi tên field đã chốt; field mới phải optional.
- Citation ID phải tồn tại trong `citations`.
- Thứ tự mảng là thứ tự hiển thị.
- Text trả về là UTF-8 và giữ đúng dấu tiếng Việt.

## 8. Lịch sử lượt tác vụ

Trong môi trường demo chưa có đăng nhập, client gửi định danh qua header
`X-User-ID`. Nếu không gửi, backend dùng `demo-user` để giữ tương thích với luồng
cũ. Header này chỉ là cơ chế phân vùng dữ liệu, không phải cơ chế xác thực; bản
production phải lấy `user_id` từ access token đã được xác minh.

Mỗi lần upload tạo một `task_id` mới, kể cả khi cùng `document_id` và cache hit.
Mỗi lần hỏi đáp cũng tạo một task độc lập. `task_id` được trả thêm trong response
upload và question.

`GET /history?limit=20&offset=0&status=completed&task_type=document_processing`

Các bộ lọc tùy chọn: `status`, `task_type`, `from_at`, `to_at`, `limit`, `offset`.
Thời gian dùng ISO 8601; kết quả sắp xếp mới nhất trước.

```json
{
  "items": [
    {
      "task_id": "7a413d74-f909-4d0f-b1aa-34b5402e352f",
      "task_type": "document_processing",
      "document_id": "sha256",
      "display_name": "bien-ban-hop.pdf",
      "status": "completed",
      "stage": "ready",
      "progress": 100,
      "cached": false,
      "created_at": "2026-07-18T07:30:00Z",
      "started_at": "2026-07-18T07:30:00Z",
      "updated_at": "2026-07-18T07:30:21Z",
      "completed_at": "2026-07-18T07:30:21Z",
      "duration_seconds": 21.0,
      "error": null
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

`GET /history/{task_id}` trả một lượt tác vụ. Backend luôn giới hạn truy vấn theo
`X-User-ID`; task thuộc người dùng khác được trả như `HISTORY_NOT_FOUND` để không
tiết lộ sự tồn tại của dữ liệu.
