# Bàn giao HAU — Intelligence và OCR fallback

## Context

Hai adapter được thiết kế tách khỏi ingestion và model client để các consumer có
thể dùng fixture/test double trước khi integration production hoàn tất.

## Contract intelligence

```python
from intelligence import IntelligenceReport, NormalizedDocument, build_intelligence

report = await build_intelligence(
    NormalizedDocument.model_validate(payload),
    call_llm=shared_call_llm,
    citation_validator=validate_citations,  # optional; whitelist nội bộ luôn chạy
)
```

- `call_llm(messages, response_model)` phải là client dùng chung và trả object
  tương thích `response_model`.
- Map chạy theo batch 7 trang mặc định; cấu hình chỉ cho phép 6–8 trang.
- Mọi output item thiếu nguồn bị loại. Citation hợp lệ phải là `chunk_id` thuộc
  document; validator ngoài chỉ có thể thu hẹp whitelist, không thể mở rộng.
- `IntelligenceReport.model_json_schema()` là JSON schema nguồn cho structured
  output. Prompt được version-control tại `src/intelligence/prompts.py`.
- `stage_timings` ghi thời gian map/reduce/validation; `quality` ghi checklist
  định lượng. `quality.passed=false` không có nghĩa report bị bịa, mà nghĩa chưa
  đủ ngưỡng nghiệm thu (4 summary sections, 10 terms, 5 questions đạt rubric).

Fixture dùng chung nằm tại `docs/fixtures/normalized_document.mock.json` và
`docs/fixtures/intelligence_report.mock.json`.

## Contract OCR

```python
from pipeline import OcrActivationPolicy, ocr_page, ocr_table

policy = OcrActivationPolicy()
if policy.should_ocr_page(native_text):
    text = ocr_page(image_bytes)

table = ocr_table(image_bytes, page=3, bbox=(10, 20, 500, 700))
markdown = table.markdown
json_payload = table.model_dump(mode="json")
```

| Quyết định router | Mặc định | Lý do |
|---|---:|---|
| OCR trang | native text dưới 80 ký tự hoặc alphanumeric ratio dưới 0.35 | Tránh OCR toàn tài liệu |
| OCR bảng | bảng ảnh, hoặc native table dưới 2 hàng/2 cột, hoặc không có text | Chỉ fallback khi extraction native không đủ cấu trúc |

PaddleOCR được lazy-load nên import pipeline và unit test không tải model.
Runtime đã được pin cho Windows, Python 3.12 và CUDA 12.6 trong
`requirements.txt`; backend tự chọn `gpu:0` khi Paddle CUDA thấy GPU và fallback
về CPU khi CUDA không khả dụng. Có thể ép thiết bị khi kiểm thử bằng
`PaddleOcrBackend(device="cpu")` hoặc `PaddleOcrBackend(device="gpu:0")`.
`PaddleOcrAdapter(backend=test_double)` cho phép test độc lập hoàn toàn bằng
`image_bytes`. Tuấn chịu trách nhiệm crop/router page/bbox trong pipeline.

## Reliability constraints

- Image bytes rỗng/hỏng gây `InvalidImageError`; table không có cell gây
  `OcrError`, không trả bảng placeholder.
- Map batch lỗi một phần vẫn cho phép reduce các batch hợp lệ; tất cả batch lỗi
  gây `IntelligenceGenerationError`.
- Không có chunk thì trả report rỗng và không gọi model.
