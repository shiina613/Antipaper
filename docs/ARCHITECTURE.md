# Kiến trúc Antipaper

## 1. Mục tiêu thiết kế

- Tạo báo cáo từ tài liệu 40+ trang trong dưới 60 giây.
- Mọi kết quả quan trọng truy ngược được đến trang và mục/điều.
- Đủ đơn giản để 5 người tích hợp trong 48 giờ.
- Có đường nâng cấp an toàn cho triển khai tại UBND.

## 2. Kiến trúc hackathon

```text
Next.js
  │ upload / polling / Q&A
  ▼
FastAPI ── Job store in-memory ── Cache theo SHA-256
  │
  ├─ Trích xuất: PyMuPDF / python-docx
  ├─ Parse cấu trúc: Chương → Mục → Điều → Khoản → Trang
  ├─ AI song song: tóm tắt / thuật ngữ / câu hỏi
  ├─ Văn bản liên quan: căn cứ trong văn bản + catalog cục bộ
  └─ Truy hồi trong RAM → Q&A → kiểm tra citation
```

Streamlit được giữ làm giao diện dự phòng nếu Next.js chưa tích hợp ổn định trước giờ 32.

## 3. Luồng xử lý

1. Kiểm tra PDF/DOCX, kích thước và MIME; tạo `document_id` từ SHA-256.
2. PDF có text layer đi thẳng qua PyMuPDF. Chỉ OCR trang gần như rỗng.
3. Bảng native dùng `Page.find_tables()`; YOLOv8 table-specific chỉ phát hiện/crop vùng bảng ảnh và không sinh nội dung OCR.
4. Tách Chương/Mục/Điều/Khoản bằng regex; mỗi chunk/bảng giữ metadata nguồn.
5. Chia tài liệu theo nhóm 6–8 trang; gọi LLM song song để tạo bản tóm tắt cục bộ.
6. Một lượt reduce tạo bối cảnh, nội dung chính, điểm quyết định và tác động.
7. Chạy song song thuật ngữ, câu hỏi và căn cứ liên quan bằng đầu ra có schema.
8. Tạo index embedding in-memory cho Q&A. Citation được lấy từ chunk, không do LLM tự sinh.
9. Lưu report theo `document_id`; frontend polling rồi hiển thị kết quả.

## 4. Mô hình dữ liệu tối thiểu

```json
{
  "chunk_id": "P12-D7-K2-C1",
  "page": 12,
  "chapter": "Chương II",
  "section": null,
  "article": "Điều 7",
  "clause": "Khoản 2",
  "text": "..."
}
```

LLM chỉ trả `chunk_id`. Backend kiểm tra ID tồn tại rồi chuyển thành “Trang 12, Điều 7, Khoản 2”. ID sai bị loại; không còn bằng chứng thì trả lời từ chối.

## 5. Ngân sách độ trễ

| Giai đoạn | Mục tiêu P95 |
|---|---:|
| Nhận file và trích xuất | 5 giây |
| Parse/chunk/index | 5 giây |
| Map summary song song | 25 giây |
| Reduce + terms + questions + related docs | 20 giây |
| Lưu và trả kết quả | 5 giây |
| Tổng | Dưới 60 giây |

Benchmark tính từ lúc backend nhận đủ file đến khi report chuyển sang `completed`. Phải ghi cấu hình máy, model và cold/warm run.

## 6. Quyết định phạm vi

| Quyết định | Lý do |
|---|---|
| Chỉ chạy YOLO trên trang cần kiểm tra bảng ảnh | Bảo vệ latency; checkpoint chỉ trả vùng `bordered`/`borderless` |
| Không có OCR fallback | Quyết định phạm vi hiện tại chỉ cho phép YOLOv8; bảng scan không có text layer sẽ không có nội dung để phân tích |
| Không dùng LangChain | Giảm abstraction, dependency và thời gian debug |
| Không dùng vector database | Một tài liệu 40–60 trang đủ nhỏ để index trong RAM |
| Không OCR tài liệu | Pipeline hiện chỉ dùng native text và YOLOv8 table detection |
| Không tìm kiếm web trực tiếp | Khó kiểm soát độ tin cậy; ưu tiên căn cứ trong tài liệu và catalog nguồn chính thống |

## 7. Độ tin cậy và an toàn

- Pydantic kiểm tra mọi output LLM; retry một lần khi sai schema.
- Lưu page/section metadata ngay từ lúc trích xuất.
- Q&A phải có citation hợp lệ hoặc từ chối.
- Prompt và log không chứa API key; không log toàn văn tài liệu.
- Demo chỉ dùng tài liệu công khai.

## 8. Nguồn dữ liệu

- Văn bản quy phạm pháp luật và Công báo từ nguồn chính thức của Chính phủ/Quốc hội.
- Nghị quyết, kế hoạch và tài liệu họp công khai của UBND tỉnh.
- Catalog phải lưu URL nguồn, số hiệu, ngày ban hành, trạng thái hiệu lực và thời điểm tải.
- Các PDF hiện có cần bổ sung metadata nguồn trước khi nộp; không suy đoán nguồn chỉ từ tên file.

## 9. Lộ trình triển khai tại UBND

| Giai đoạn | Phạm vi |
|---|---|
| Hackathon | Một tài liệu/lần, dữ liệu công khai, cache cục bộ |
| Pilot 1 đơn vị | SSO, phân quyền, audit log, object storage, reviewer thuật ngữ |
| Triển khai thật | On-premise/approved cloud, mã hóa, retention policy, HA, giám sát chất lượng và chi phí |
