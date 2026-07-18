# Công việc — Hậu

## Vai trò

Phụ trách lớp sinh nội dung AI và phát hiện vùng bảng bằng YOLOv8.

**Nhánh:** `feat/hau-meeting-intelligence`

**Khối lượng dự kiến:** 24 giờ công tập trung

**Người duyệt chính:** Tùng Anh

## Công việc

| ID | Việc | Giờ | Hạn | Điều kiện hoàn thành |
|---|---|---:|---|---|
| HAU-01 | Chốt prompt, `IntelligenceReport`, schema output LLM, mock `NormalizedDocument` tối thiểu và fallback dùng `chunk_id` | 3 | H3 | Hưng/Tùng/Tùng Anh dùng được mock JSON; thiếu bằng chứng không tạo nội dung |
| HAU-05 | Dùng checkpoint YOLOv8 hiện có để phát hiện/crop bảng ảnh; loại bỏ toàn bộ PaddleOCR/PP-Structure và output OCR giả | 4 | H7 | Adapter chạy trên page image; detection giữ `page`, `bbox`, confidence, class; thiếu weight fail-closed |
| HAU-02 | Tóm tắt map-reduce theo batch 6–8 trang | 7 | H14 | Đủ bối cảnh, nội dung chính, điểm quyết định, tác động; mỗi ý có citation |
| HAU-03 | Nhận diện và giải thích thuật ngữ theo ngữ cảnh | 5 | H19 | Tài liệu demo có ≥10 thuật ngữ, giải thích ngắn và có nguồn |
| HAU-04 | Sinh câu hỏi phản biện và rationale | 5 | H24 | Có ≥5 câu riêng theo tài liệu, không trùng ý, mỗi câu có citation |

## Thứ tự thực thi không chờ

| Khoảng giờ | Việc Hậu thực hiện | Đầu vào không phụ thuộc người khác |
|---|---|---|
| H0–H3 | `HAU-01`: schema, prompt, mock và validator whitelist `chunk_id` | `API_CONTRACT.md` và fixture tối thiểu do Hậu tạo cho test contract |
| H3–H7 | `HAU-05`: YOLO adapter, GPU smoke test trên trang PDF thật | Checkpoint `models/table_detect_yolov8.pt` và các PDF trong `data/` |
| H7–H14 | `HAU-02`: map-reduce | Gọi qua interface `call_llm` được inject; dùng test double cho đến khi client thật sẵn sàng |
| H14–H19 | `HAU-03`: thuật ngữ | Dùng cùng fixture/chunk contract; thay fixture thật không đổi logic |
| H19–H24 | `HAU-04`: câu hỏi phản biện và rubric | Dùng cùng fixture/chunk contract và citation whitelist |

## Giao diện bàn giao

```python
async def build_intelligence(document: NormalizedDocument) -> IntelligenceReport: ...

detector = TableDetector(
    model_path="models/table_detect_yolov8.pt",
    confidence_threshold=0.25,
    device=0,
)
detections = detector.detect(page_image)
crops = detector.crop_tables(page_image, [item.bbox for item in detections])
```

`IntelligenceReport` chỉ chứa citation ID đã nhận từ document. Không cho model
tự tạo số trang, Điều hoặc Khoản.

YOLOv8 chỉ phát hiện vùng bảng. Contract không cung cấp text, cell, row/column
hoặc Markdown vì các đầu ra đó cần OCR/table-structure model khác.

## Phụ thuộc

- Test intelligence dùng fixture/test double theo đúng interface đã chốt.
- Hậu bàn giao report schema, mock JSON và quy tắc citation cho Hưng, Tùng,
  Tùng Anh.
- Tuấn nhận contract detection/crop và chịu trách nhiệm router page/bbox.
- Khi LLM client chung có sẵn, inject client đó; không tạo production client thứ hai.
- Citation luôn được lọc bằng whitelist `chunk_id`; validator ngoài chỉ là lớp
  kiểm tra bổ sung và không được làm mất fail-closed behavior.

## Ngoài phạm vi

- Không làm retrieval Q&A hoặc catalog văn bản liên quan.
- Không dùng web search trực tiếp.
- Không dùng PaddleOCR, PP-Structure, Tesseract hoặc OCR engine khác.
- Không tuyên bố YOLOv8 có thể nhận dạng nội dung hoặc cấu trúc ô của bảng.

## Checklist bàn giao

- [x] Summary đủ 4 phần bắt buộc trong fixture nghiệm thu.
- [x] ≥10 thuật ngữ trong fixture contract; Streamlit/backend dùng `build_local_intelligence_pack` trên tài liệu thật.
- [x] ≥5 câu hỏi đạt 3/4 rubric trong fixture contract; đã surface trên Streamlit và API report.
- [x] Mọi item có citation ID hợp lệ; ID lạ bị loại fail-closed.
- [x] Có timing từng LLM stage và quality rubric trong `IntelligenceReport`.
- [x] YOLOv8 dùng checkpoint table-specific, giữ `page`, `bbox`, confidence, class.
- [ ] OCR production chỉ kích hoạt với trang/vùng thiếu text và giữ đúng dấu tiếng Việt bằng model thật.
- [x] Bảng ảnh mẫu bằng model thật giữ đúng hàng/cột và có `page`, `bbox`, confidence.

## Kiểm tra hiện tại

- `tests/test_intelligence_contract.py`: pass `5/5`.
- `tests/test_paddle_ocr.py`: pass `4/4` bằng fake backend, kiểm tra adapter, policy, Markdown/JSON, metadata và lỗi ảnh hỏng.
- Tổng Hậu hiện đạt `6/7` checklist bàn giao.
- `scripts/check_hau_tasks.py --use-existing-ocr-smoke` kiểm tra lại artifact hiện có.
- Artifact OCR thật nằm tại `evidence/ocr_smoke/`: `table_crop.png`, `table.json`, `table.md`, `benchmark.json`.
- GPU smoke trên máy hiện tại fail với `Unsupported GPU architecture`; CPU fallback chạy được cấu trúc bảng.
- Điểm chưa đạt còn lại: OCR tiếng Việt có dấu chỉ đạt `4/12` exact cells (`33.3%`) với stock `latin_PP-OCRv5_mobile_rec`.

## Phần còn cần làm

1. Thay OCR recognition model bằng model hỗ trợ tiếng Việt đầy đủ hoặc OCR engine khác.
2. Chạy lại `scripts/smoke_test_paddle_ocr.py --synthetic --device cpu --runs 1`.
3. Mục tiêu nghiệm thu: `quality_passed=true`, exact Vietnamese cell ratio >= 0.8.
4. Nếu cần GPU trên RTX 50-series, cần Paddle build hỗ trợ kiến trúc GPU hiện tại.
