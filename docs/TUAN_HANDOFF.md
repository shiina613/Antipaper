# Bàn giao Tuấn — Ingestion và LLM Client

## Đã hoàn thành

- Thêm ingestion entry point:
  - `src/ingestion/document_ingestor.py`
  - `ingest_document(path, options) -> NormalizedDocument`
- PDF ingestion:
  - Dùng YOLOv8 table pipeline khi có `models/table_detect_yolov8.pt`.
  - Fallback native PyMuPDF khi chưa có weights để test/CI không phụ thuộc model.
  - Native path có `page.find_tables()` và xuất bảng markdown.
- DOCX ingestion:
  - Dùng `python-docx`.
  - Paragraphs và tables đều được normalize thành chunks.
- Chunk/citation:
  - `chunk_id`: `P{page}-D{index}`.
  - Citation map key luôn trùng `chunk_id`.
  - Parse `Chương/CHUONG`, `Điều/DIEU`, `Khoản/KHOAN`, và dòng `1.`.
- LLM client dùng chung:
  - `src/llm/client.py`
  - OpenAI-compatible JSON response.
  - Env config: `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`.
  - Timeout retry và Pydantic schema validation.
- Fixture:
  - `docs/fixtures/normalized_document.01.json`
  - Sinh từ `data/01.pdf`, gồm 38 trang và 111 chunks.

## Kiểm tra đã chạy

```powershell
python -m pytest tests/test_tuan_ingestion.py tests/test_llm_client.py tests/test_intelligence_contract.py -q
```

Kết quả: `12 passed`.

```powershell
python -m compileall -q src tests scripts
git diff --check
```

Kết quả: pass.

## Lưu ý

- Ingestion không gọi LLM và deterministic.
- OCR/Paddle GPU không thuộc phạm vi Tuấn; ingestion chỉ tích hợp được với adapter/router sau khi OCR fallback ổn định.
- YOLOv8 vẫn được giữ trong fast path PDF khi weights tồn tại, đúng yêu cầu tiếp tục dùng YOLOv8.
