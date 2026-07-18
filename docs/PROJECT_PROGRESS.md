# Tiến độ hiện tại

**Cập nhật:** 18/07/2026
**Baseline:** nhánh `tuan`, commit `ac624f3`

File này chỉ ghi nhận việc đã làm, đang làm và chưa làm. Kế hoạch nằm trong `BUILD_PLAN_48H.md`; phân công nằm trong các file `TASKS_*.md`.

## Đã làm

| Hạng mục | Bằng chứng | Ghi chú |
|---|---|---|
| Khung xử lý PDF native | `src/pipeline/` | Có trích xuất theo trang, phát hiện vùng bảng và ghép nội dung |
| Streamlit MVP | `app.py` | Có upload PDF, các tab kết quả và chat mẫu |
| Logic intelligence mẫu | `src/intelligence/meeting_intelligence.py` | Rule-based; chưa phải AI production |
| Next.js dashboard tĩnh | `frontend/app/page.tsx` | Có layout demo; chưa nối backend |
| Tài liệu PDF 40+ trang | Kho `data/` | Đã có nhiều file đạt số trang; chưa khóa tên tài liệu demo trong code |
| Bộ tài liệu chuẩn bị hackathon | `docs/` và `problem.txt` | Đã có kiến trúc, tech stack, API, kế hoạch, test và task từng người |

## Đang làm

| Hạng mục | Trạng thái |
|---|---|
| Chuẩn hóa hợp đồng dữ liệu và API | Đã thiết kế trong tài liệu, chưa triển khai vào code |
| Chuẩn bị môi trường chạy chung | Chưa xác nhận đủ dependencies, model API key và cấu hình frontend/backend |
| Kiểm tra dữ liệu demo | Đã xác nhận số trang và text layer; chưa tạo golden answers |

## Chưa làm

| Hạng mục | Điều kiện hoàn thành |
|---|---|
| Nhập DOCX | Trả cùng schema với PDF và giữ cấu trúc đoạn/tiêu đề |
| Bảng ảnh/scan | Chỉ phát hiện/crop bằng YOLOv8; trang không có text layer không được OCR |
| Phát hiện bảng ảnh/scan | YOLOv8 table-specific trả bbox/confidence/class và crop; không có OCR/cell/Markdown |
| Tóm tắt LLM có cấu trúc | Đủ 4 mục bắt buộc, có citation và schema validation |
| Giải thích thuật ngữ | Ít nhất 10 thuật ngữ đúng ngữ cảnh, có nguồn |
| Câu hỏi phản biện | Ít nhất 5 câu riêng theo tài liệu, có lý do và nguồn |
| Văn bản liên quan | Trích căn cứ và đối chiếu catalog tài liệu công khai |
| Q&A grounded | Retrieval theo nội dung, trả trang + mục/điều hoặc từ chối |
| FastAPI và job processing | Upload, status, report, question hoạt động theo API contract |
| Tích hợp Next.js | Upload thật, progress, report, viewer và chat |
| Benchmark 40+ trang | Tài liệu tại `DEMO_DOCUMENT_PATH` hoàn tất dưới 60 giây, có log cấu hình máy |
| Kiểm thử nghiệm thu | Đạt toàn bộ checklist trong `ACCEPTANCE_TESTS.md` |
| Deck có số liệu thật | Thay toàn bộ placeholder bằng benchmark và ảnh demo |

## Vướng mắc hiện tại

- Đã xác nhận checkpoint `models/table_detect_yolov8.pt` có class `bordered` và `borderless`; runtime GPU phải được kiểm tra bằng smoke test.
- Chưa chốt nhà cung cấp LLM, model, API key và hạn mức gọi.
- Chưa có golden set để đo độ đúng của thuật ngữ, câu hỏi và citation.
