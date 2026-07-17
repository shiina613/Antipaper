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

## 3. Lấy báo cáo

`GET /documents/{document_id}/report`

```json
{
  "document_id": "sha256-prefix",
  "file_name": "<tên-file-gốc>",
  "page_count": 44,
  "processing_seconds": 38.2,
  "summary": {
    "context": [{"text": "...", "citation_ids": ["P1-D1"]}],
    "main_content": [{"text": "...", "citation_ids": ["P3-D4"]}],
    "decision_points": [{"text": "...", "citation_ids": ["P20-D12"]}],
    "impact": [{"text": "...", "citation_ids": ["P30-D18"]}]
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
      "source": "cited_in_document",
      "reason": "...",
      "citation_ids": ["P1-D2"]
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

Trả text và các block để frontend mở đúng trang/vùng. Trong MVP có thể hiển thị text trang thay cho PDF canvas.

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
