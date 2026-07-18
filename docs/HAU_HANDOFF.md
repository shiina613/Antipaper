# Bàn giao HAU — Intelligence và YOLOv8 table detection

## Context

Lớp intelligence được tách khỏi ingestion và model client để các consumer có
thể dùng fixture/test double trước khi tích hợp production. Theo quyết định kỹ
thuật mới, toàn bộ PaddleOCR/PP-Structure đã được loại bỏ; pipeline chỉ dùng
YOLOv8 hiện có để phát hiện và cắt vùng bảng.

## Contract intelligence

```python
from intelligence import IntelligenceReport, NormalizedDocument, build_intelligence

report = await build_intelligence(
    NormalizedDocument.model_validate(payload),
    call_llm=shared_call_llm,
    citation_validator=validate_citations,
)
```

- `call_llm(messages, response_model)` phải là client dùng chung và trả object
  tương thích `response_model`.
- Map chạy theo batch 7 trang mặc định; cấu hình chỉ cho phép 6–8 trang.
- Output thiếu nguồn bị loại. Citation hợp lệ phải là `chunk_id` thuộc document;
  validator ngoài chỉ có thể thu hẹp whitelist, không thể mở rộng.
- `IntelligenceReport.model_json_schema()` là JSON schema cho structured output.
- `stage_timings` ghi map/reduce/validation; `quality` ghi checklist định lượng.

Fixture dùng chung:

- `docs/fixtures/normalized_document.mock.json`
- `docs/fixtures/intelligence_report.mock.json`

## Contract YOLOv8

```python
from pipeline import TableDetector

detector = TableDetector(
    "models/table_detect_yolov8.pt",
    confidence_threshold=0.25,
    device=0,
)
detections = detector.detect(page_image)
crops = detector.crop_tables(page_image, [item.bbox for item in detections])
```

Model đã xác nhận là checkpoint table-specific với hai lớp `bordered` và
`borderless`. Model path là bắt buộc; thiếu checkpoint sẽ fail-closed thay vì
tự tải weight COCO chung.

| Trường | Có từ YOLOv8 | Ý nghĩa |
|---|---:|---|
| `bbox` | Có | Vùng bảng trong hệ tọa độ ảnh |
| `confidence` | Có | Độ tin cậy detection |
| `class_id` | Có | `bordered` hoặc `borderless` |
| crop ảnh | Có | Ảnh con phục vụ consumer tiếp theo |
| text tiếng Việt | Không | YOLO không nhận dạng ký tự |
| row/column/cell | Không | YOLO không nhận dạng cấu trúc bảng |
| Markdown/JSON nội dung | Không | Không được tạo placeholder hoặc suy diễn |

`PdfProcessingPipeline` giữ nguyên native PDF text và chỉ đính kèm detection
metadata. Pipeline không che vùng bảng rồi thay bằng nội dung rỗng, nhờ đó tránh
mất text layer khi không có OCR thay thế.

## Reliability constraints

- Không có model table-specific thì dừng với `YoloModelConfigurationError`.
- Bounding box được clip vào kích thước ảnh; vùng rỗng bị loại.
- Không còn export `ocr_page`, `ocr_table`, `PaddleOcrAdapter` hay
  `table_to_markdown` placeholder.
- Map batch lỗi một phần vẫn reduce các batch hợp lệ; tất cả batch lỗi gây
  `IntelligenceGenerationError`.
- Không có chunk thì trả report rỗng và không gọi model.

## Giới hạn nghiệm thu HAU-05

HAU-05 theo mô tả gốc yêu cầu OCR tiếng Việt, đúng hàng/cột và Markdown/JSON.
YOLOv8 thuần không thể đáp ứng các đầu ra này. Phần đạt được sau thay đổi phạm vi
là detection/crop trên ảnh thật với `page`, `bbox`, `confidence` và class; phần
OCR nội dung được đánh dấu không đạt thay vì tạo dữ liệu giả.
