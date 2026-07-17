# Công việc — Tùng

## Vai trò

Phụ trách trải nghiệm người dùng, tích hợp giao diện, demo xuyên suốt và hồ sơ trình bày.

**Nhánh:** `feat/tung-meeting-ui`
**Khối lượng dự kiến:** 24 giờ công tập trung
**Người duyệt chính:** Hưng

## Công việc

| ID | Việc | Giờ | Hạn | Điều kiện hoàn thành |
|---|---|---:|---|---|
| TUNG-01 | API client, upload PDF/DOCX, polling và progress/error | 4 | H12 | Dùng mock rồi API thật; loading/retry đầy đủ |
| TUNG-02 | Màn report: 4 phần summary, terms, questions, related docs | 6 | H20 | Không còn hard-code trong luồng chính; responsive và dễ đọc |
| TUNG-03 | Citation chips, highlight inline và viewer đúng trang/excerpt | 5 | H24 | Click từ report/chat đến đúng nguồn; thuật ngữ có giải thích inline |
| TUNG-04 | Chat cuộc họp và trạng thái thiếu bằng chứng | 4 | H28 | Gửi câu hỏi, hiển thị answer/citations/latency; xử lý lỗi |
| TUNG-05 | E2E, video, rehearsal và cập nhật one-page deck | 5 | H40 | Luồng demo ≤3 phút; deck dùng số liệu thật; có bản fallback |

## Luồng demo bắt buộc

1. Upload tài liệu tại `$DEMO_DOCUMENT_PATH`.
2. Theo dõi xử lý và hiển thị thời gian.
3. Xem summary, 10 terms, 5 questions và related docs.
4. Bấm một citation mở đúng trang/Điều.
5. Hỏi một câu có đáp án và một câu ngoài phạm vi.

## Phụ thuộc

- Dùng mock JSON theo `API_CONTRACT.md` ngay từ H2.
- Nhận endpoints từ Hưng tại H8.
- Nhận report schema từ Hậu và Q&A schema từ Tùng Anh; không tự suy diễn field.

## Ngoài phạm vi

- Không dành thời gian cho pricing, testimonial hoặc animation không phục vụ demo.
- Không viết lại design system.
- Không che lỗi backend bằng dữ liệu hard-code sau H24.

## Checklist bàn giao

- [ ] Luồng chính không dùng dữ liệu tĩnh.
- [ ] Loading/error/retry hoạt động.
- [ ] Citation mở đúng nguồn; thuật ngữ/điều khoản có giải thích inline.
- [ ] Demo chính và Streamlit fallback đã rehearsal.
- [ ] Deck và video dùng kết quả benchmark thật.
