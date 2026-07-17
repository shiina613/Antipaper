# Yêu cầu sản phẩm Antipaper

## 1. Mục tiêu

Giúp cán bộ nắm nội dung và chuẩn bị thảo luận từ tài liệu họp 40–60 trang trong vài phút, đồng thời kiểm chứng được mọi kết luận từ văn bản gốc.

## 2. Người dùng và nhu cầu

| Người dùng | Việc cần hoàn thành |
|---|---|
| Lãnh đạo/chủ trì | Biết điểm phải quyết định, tác động, rủi ro và câu hỏi cần đặt |
| Cán bộ tham mưu | Kiểm tra căn cứ, điều khoản, trách nhiệm và tài liệu liên quan |
| Thư ký cuộc họp | Tra cứu nhanh câu trả lời và mở đúng nguồn trong cuộc họp |

## 3. Hành trình chính

```text
Tải tài liệu → Chờ dưới 60 giây → Đọc báo cáo → Kiểm tra citation
→ Chuẩn bị câu hỏi → Hỏi đáp trong cuộc họp
```

## 4. Yêu cầu chức năng

| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-01 | Upload PDF/DOCX, báo lỗi file rõ ràng | P0 |
| FR-02 | Tóm tắt bối cảnh, nội dung chính, điểm quyết định, tác động | P0 |
| FR-03 | Phát hiện và giải thích inline ít nhất 10 thuật ngữ/điều khoản | P0 |
| FR-04 | Sinh ít nhất 5 câu hỏi phản biện theo tài liệu | P0 |
| FR-05 | Hỏi đáp tiếng Việt với trang + mục/điều | P0 |
| FR-06 | Bấm citation để xem excerpt; highlight thuật ngữ/điều khoản trong viewer | P0 |
| FR-07 | Gợi ý văn bản liên quan có số hiệu, nguồn và lý do | P0 |
| FR-08 | Cache file đã xử lý và hiển thị trạng thái tiến độ | P1 |
| FR-09 | OCR trang scan và đọc bảng phức tạp | P2 |

## 5. Yêu cầu phi chức năng

| ID | Yêu cầu | Mức đạt |
|---|---|---|
| NFR-01 | Độ trễ | Report cho `$DEMO_DOCUMENT_PATH` dưới 60 giây |
| NFR-02 | Groundedness | Mọi ý quan trọng có citation hợp lệ hoặc hệ thống từ chối |
| NFR-03 | Citation | Precision mục tiêu ≥90% trên golden set |
| NFR-04 | Khả dụng | Luồng demo hoàn tất ba lần liên tiếp không lỗi P0/P1 |
| NFR-05 | Bảo mật | Không log key/toàn văn; demo chỉ dùng dữ liệu công khai |
| NFR-06 | Tiếng Việt | Text, dấu và thuật ngữ hiển thị đúng UTF-8 |

## 6. Nguyên tắc sản phẩm

- Citation-first: trích xuất cấu trúc và nguồn trước khi sinh nội dung.
- Meeting-first: ưu tiên điểm quyết định, trách nhiệm, tác động và rủi ro; không chỉ rút gọn văn bản.
- Refuse-by-default: thiếu bằng chứng thì nói rõ không đủ thông tin.
- Human-verifiable: mọi kết quả phải mở lại được đoạn nguồn trong tối đa một thao tác.

## 7. Trường hợp biên bắt buộc xử lý

- File sai định dạng, quá lớn, có mật khẩu hoặc hỏng.
- PDF có trang rỗng/text layer kém.
- Điều/Khoản kéo dài qua nhiều trang.
- Câu hỏi cần tổng hợp nhiều đoạn hoặc không thuộc tài liệu.
- LLM timeout, output sai schema hoặc trả citation ID không tồn tại.
- Upload lại cùng file và hai job chạy đồng thời.

## 8. Không thuộc phạm vi 48 giờ

- Thay thế ý kiến pháp lý hoặc tự đưa ra quyết định hành chính.
- Kho tri thức toàn quốc cập nhật thời gian thực.
- Phân quyền, chữ ký số, tích hợp văn thư và lưu trữ hồ sơ production.
- Cam kết hoạt động với mọi PDF scan/bảng phức tạp.

## 9. Điều kiện hoàn tất MVP

MVP chỉ được coi là hoàn tất khi toàn bộ P0 pass theo `ACCEPTANCE_TESTS.md`, report và deck dùng kết quả thật, và demo có phương án fallback đã rehearsal.
