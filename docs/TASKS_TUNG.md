# Công việc — Tùng

## Vai trò

Phụ trách trải nghiệm người dùng, tích hợp giao diện, demo xuyên suốt và hồ sơ trình bày.

**Nhánh:** `feat/tung-meeting-ui`
**Khối lượng dự kiến:** 18 giờ công tập trung (12 giờ baseline sau khi tái sử dụng dữ liệu/artifact có sẵn + 6 giờ chuyển từ Hùng)
**Người duyệt chính:** Hưng

## Công việc

| ID | Việc | Giờ | Hạn | Điều kiện hoàn thành |
|---|---|---:|---|---|
| TUNG-01 | API client, upload PDF/DOCX, polling và progress/error | 2 | H12 | Tái sử dụng dữ liệu/artifact có sẵn; dùng mock rồi API thật; loading/retry đầy đủ |
| TUNG-02 | Màn report: 4 phần summary, terms, questions, related docs | 3 | H20 | Tái sử dụng dữ liệu/artifact có sẵn; không còn hard-code trong luồng chính; responsive và dễ đọc |
| TUNG-03 | Citation chips, highlight inline và viewer đúng trang/excerpt | 3 | H24 | Click từ report/chat đến đúng nguồn; thuật ngữ có giải thích inline |
| TUNG-04 | Chat cuộc họp và trạng thái thiếu bằng chứng | 2 | H28 | Gửi câu hỏi, hiển thị answer/citations/latency; xử lý lỗi |
| TUNG-05 | E2E, video, rehearsal và cập nhật one-page deck | 2 | H40 | Luồng demo ≤3 phút; deck dùng số liệu thật; có bản fallback |
| TUNG-06 | Benchmark từng stage, phân tích bottleneck và nghiệm thu concurrency/timeout | 6 | H32 | Có cold + 3 warm runs, ghi cấu hình máy/commit; ít nhất một run hợp lệ dưới 60 giây; issue backend chuyển Hùng xử lý |

## Luồng demo bắt buộc

1. Upload tài liệu tại `$DEMO_DOCUMENT_PATH`.
2. Theo dõi xử lý và hiển thị thời gian.
3. Xem summary, 10 terms, 5 questions và related docs.
4. Bấm một citation mở đúng trang/Điều.
5. Hỏi một câu có đáp án và một câu ngoài phạm vi.

## Phụ thuộc

- Dùng report mock JSON do Hậu chốt theo `API_CONTRACT.md` tại H3; trước mốc này dựng layout bằng type trong contract, không tự thêm field.
- Nhận endpoints từ Hưng tại H8.
- Nhận report schema từ Hậu tại H3 và Q&A schema từ Tùng Anh trước H12; không tự suy diễn field.
- Nhận stage timing và hỗ trợ xử lý bottleneck từ Hùng để hoàn thành `TUNG-06` trước H32.

## Ngoài phạm vi

- Không dành thời gian cho pricing, testimonial hoặc animation không phục vụ demo.
- Không viết lại design system.
- Không che lỗi backend bằng dữ liệu hard-code sau H24.

## Checklist bàn giao

- [ ] Luồng chính không dùng dữ liệu tĩnh.
- [ ] Loading/error/retry hoạt động.
- [ ] Citation mở đúng nguồn; thuật ngữ/điều khoản có giải thích inline.
- [ ] Benchmark có cold + 3 warm runs, cấu hình máy, commit và kết luận bottleneck.
- [ ] Demo chính và Streamlit fallback đã rehearsal.
- [ ] Deck và video dùng kết quả benchmark thật.
