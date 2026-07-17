# Kế hoạch phát triển 48 giờ

## 1. Mục tiêu khóa

Trước giờ 40 phải có một luồng ổn định:

```text
Upload `$DEMO_DOCUMENT_PATH` → báo cáo dưới 60 giây → 10 thuật ngữ → 5 câu hỏi
→ văn bản liên quan → hỏi đáp có citation → bấm mở đúng nguồn
```

## 2. Thứ tự ưu tiên

| Mức | Phạm vi |
|---|---|
| P0 — bắt buộc | PDF/DOCX, tóm tắt <60 giây, 10 thuật ngữ, 5 câu hỏi, văn bản liên quan, Q&A có nguồn, viewer, architecture/deck |
| P1 — cần có | Cache, trạng thái tiến độ, lỗi/từ chối rõ ràng và lexical fallback |
| P2 — nếu còn giờ | OCR trang scan, bảng phức tạp, UI animation |
| Không làm | Train model, auth production, vector DB, distributed queue |

## 3. Dòng thời gian

| Mốc | Việc phải xong | Cổng kiểm tra |
|---|---|---|
| H0–H2 | Chốt LLM, schema, API, tài liệu demo, branch | Cả đội chạy được skeleton và đọc `API_CONTRACT.md` |
| H2–H8 | Ingestion, API skeleton, LLM mock, frontend mock | Upload trả `document_id`; report mock hiển thị đúng |
| H8–H16 | Parser Điều/Khoản, summary LLM, retrieval, UI thật | Luồng PDF → summary thật chạy end-to-end |
| H16–H24 | Terms, questions, related docs, Q&A, citation viewer | Đủ toàn bộ tính năng P0 trên tài liệu demo đã chốt |
| H24–H32 | Cache, timeout, benchmark, DOCX, sửa tích hợp | Ba lần chạy liên tiếp không lỗi; có một run <60 giây |
| H32 | Khóa tính năng | Không thêm dependency hoặc tính năng mới |
| H32–H40 | Acceptance test, sửa P0/P1, deploy, điền deck | Tất cả test bắt buộc có evidence |
| H40–H44 | Rehearsal demo và tình huống lỗi | Demo chính và fallback đều chạy được |
| H44–H48 | Buffer, quay demo, đóng gói nộp | Tag/commit cuối, deck và architecture khớp code |

## 4. Nhịp tích hợp

- Họp 10 phút tại H0, H8, H16, H24, H32 và H40.
- Merge vertical slice ít nhất mỗi 8 giờ; PR nhỏ, một người review.
- Mỗi cập nhật ghi: `Đã xong`, `Tiếp theo`, `Vướng mắc`, `Bằng chứng`.
- Schema/API thay đổi phải cập nhật tài liệu trước code consumer.

## 5. Cổng phát hành

| Cổng | Điều kiện |
|---|---|
| G1 — H8 | Backend và frontend giao tiếp bằng mock contract |
| G2 — H16 | Tóm tắt thật có citation trên `$DEMO_DOCUMENT_PATH` |
| G3 — H24 | Đủ 4 năng lực sản phẩm, chưa yêu cầu đẹp |
| G4 — H32 | Luồng chính ổn định và đạt ít nhất một benchmark <60 giây |
| G5 — H40 | Acceptance pass; deck dùng số liệu thật |

## 6. Phương án dự phòng

| Sự cố | Chuyển phương án |
|---|---|
| Next.js chưa ổn tại H32 | Demo bằng Streamlit, giữ FastAPI nếu hoạt động |
| Embedding API lỗi | Retrieval lexical theo từ khóa/Điều/Khoản |
| LLM map-reduce quá chậm | Tăng batch, giảm số map call, cache kết quả demo |
| Related-doc catalog chưa xong | Chỉ hiển thị căn cứ được trích trực tiếp từ tài liệu |
| OCR/bảng gây chậm | Tắt khỏi luồng demo; dùng PDF có text layer |
| Model chính lỗi | Đổi sang model fallback đã test trước H24 |

## 7. Quy tắc Git

- Mỗi người dùng branch ghi trong `TASKS_*.md`.
- Commit gắn mã task, ví dụ `HAU-02 add structured summary`.
- Không commit `.env`, artifacts, file upload tạm hoặc API key.
- Không merge code không chạy được vào nhánh tích hợp sau H32.
