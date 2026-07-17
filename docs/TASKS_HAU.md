# Công việc — Hậu

## Vai trò

Phụ trách lớp sinh nội dung AI và OCR fallback theo trang.

**Nhánh:** `feat/hau-meeting-intelligence`
**Khối lượng dự kiến:** 24 giờ công tập trung
**Người duyệt chính:** Tùng Anh

## Công việc

| ID | Việc | Giờ | Hạn | Điều kiện hoàn thành |
|---|---|---:|---|---|
| HAU-01 | Prompt, schema đầu ra và fallback chất lượng dùng `chunk_id` | 3 | H6 | Output đúng schema; thiếu bằng chứng không tạo nội dung |
| HAU-02 | Tóm tắt map-reduce theo batch 6–8 trang | 7 | H16 | Đủ bối cảnh, nội dung chính, điểm quyết định, tác động; mỗi ý có citation |
| HAU-03 | Nhận diện và giải thích thuật ngữ theo ngữ cảnh | 5 | H20 | Tài liệu demo có ≥10 thuật ngữ, giải thích ngắn và có nguồn |
| HAU-04 | Sinh câu hỏi phản biện và rationale | 5 | H24 | Có ≥5 câu riêng theo tài liệu, không trùng ý, mỗi câu có citation |
| HAU-05 | OCR text và bảng ảnh bằng PaddleOCR PP-StructureV3 | 4 | H30 | Chỉ OCR vùng cần thiết; một bảng mẫu giữ đúng hàng/cột và xuất Markdown/JSON |

## Giao diện bàn giao

```python
async def build_intelligence(document: NormalizedDocument) -> IntelligenceReport: ...
def ocr_page(image_bytes: bytes) -> str: ...
def ocr_table(image_bytes: bytes) -> TableData: ...
```

`IntelligenceReport` chỉ chứa citation ID đã nhận từ document. Không cho model tự tạo số trang, Điều hoặc Khoản.

## Phụ thuộc

- Dùng normalized fixture của Tuấn từ H10.
- Nhận ảnh trang/bbox bảng và ngưỡng kích hoạt OCR từ pipeline của Tuấn.
- Dùng LLM client chung do Tuấn bàn giao; không tạo client thứ hai.
- Dùng citation validator của Tùng Anh trước khi trả report.
- Bàn giao schema report cho Hưng và Tùng chậm nhất H8, có mock JSON.

## Ngoài phạm vi

- Không làm retrieval Q&A hoặc catalog văn bản liên quan.
- Không dùng web search trực tiếp.
- Không OCR toàn tài liệu; quyết định OCR theo chất lượng text và loại bảng, không theo tên file.

## Checklist bàn giao

- [ ] Summary đủ 4 phần bắt buộc.
- [ ] ≥10 thuật ngữ đạt review.
- [ ] ≥5 câu hỏi đạt 3/4 rubric.
- [ ] Mọi item có citation ID hợp lệ.
- [ ] Có timing từng LLM stage và pass rubric chất lượng.
- [ ] OCR chỉ kích hoạt với trang/vùng thiếu text, giữ đúng dấu tiếng Việt.
- [ ] Bảng ảnh mẫu giữ đúng hàng/cột và có `page`, `bbox`, confidence.
