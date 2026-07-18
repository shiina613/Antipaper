# Kiểm thử nghiệm thu

## 1. Dữ liệu chuẩn

| Vai trò | Biến cấu hình | Tiêu chí chọn |
|---|---|---|
| Demo chính | `DEMO_DOCUMENT_PATH` | PDF công khai ≥40 trang, có text layer, cấu trúc pháp lý/hành chính rõ |
| Demo dự phòng | `BACKUP_DOCUMENT_PATH` | PDF công khai ≥40 trang, khác chủ đề với demo chính |
| Stress test | `STRESS_DOCUMENT_PATH` | PDF ≥60 trang để đo khả năng mở rộng |
| Smoke test | `SMOKE_DOCUMENT_PATH` | PDF ngắn 1–5 trang để kiểm tra nhanh |

Tên file không được ghi cứng trong code, test hoặc task. Mọi đường dẫn đọc từ biến môi trường. Không đổi tài liệu demo sau H24 trừ khi file hỏng hoặc có vấn đề nguồn dữ liệu.

## 2. Bảng nghiệm thu

| ID | Kiểm thử | Điều kiện đạt | Bằng chứng |
|---|---|---|---|
| AT-01 | Upload | Nhận PDF và DOCX; file sai có lỗi rõ | Ảnh/video + response API |
| AT-02 | Hiệu năng | `$DEMO_DOCUMENT_PATH` tạo report dưới 60 giây | Log cold/warm run và cấu hình máy |
| AT-03 | Tóm tắt | Đủ bối cảnh, nội dung chính, điểm quyết định, tác động | Report JSON + review tay |
| AT-04 | Thuật ngữ | Ít nhất 10 mục đúng ngữ cảnh, có citation | Phiếu chấm của 2 người |
| AT-05 | Câu hỏi | Ít nhất 5 câu đạt rubric và không trùng ý | Report + phiếu chấm |
| AT-06 | Văn bản liên quan | Có số hiệu/tên, lý do và nguồn trong tài liệu/catalog | Report + citation |
| AT-07 | Q&A | Trả tiếng Việt, dẫn đúng trang/mục/điều | Bộ 10 câu hỏi vàng |
| AT-08 | Từ chối | 3 câu ngoài tài liệu đều bị từ chối | Log response |
| AT-09 | Citation viewer | Bấm citation mở đúng trang/excerpt; thuật ngữ có giải thích inline | Video E2E |
| AT-10 | Hồ sơ nộp | Architecture và deck khớp hệ thống thật | Checklist cuối |
| AT-11 | OCR bảng ảnh | Bảng mẫu giữ đúng số hàng/cột, nội dung chính và citation trang | JSON/Markdown + review tay |

## 3. Cách đo dưới 60 giây

1. Ghi CPU, RAM, GPU nếu có, mạng, model và phiên bản commit.
2. Bắt đầu đo khi backend nhận đủ bytes của file.
3. Kết thúc khi report chuyển sang `completed` và frontend có thể lấy kết quả.
4. Chạy một cold run và ba warm run; báo cáo từng lần, không chỉ báo cáo lần nhanh nhất.
5. Cache hit phải được ghi riêng, không dùng làm bằng chứng duy nhất.

## 4. Rubric chất lượng

### Thuật ngữ

Mỗi thuật ngữ đạt khi: thật sự chuyên ngành/quan trọng, giải thích đúng ngữ cảnh, dễ hiểu và citation hỗ trợ trực tiếp. Yêu cầu ít nhất 10 mục được cả hai reviewer chấp nhận.

### Câu hỏi phản biện

Chấm mỗi câu theo bốn tiêu chí, mỗi tiêu chí 0 hoặc 1:

- Cụ thể với tài liệu.
- Thúc đẩy quyết định hoặc làm rõ trách nhiệm/rủi ro.
- Có thể dùng trong cuộc họp.
- Có citation hỗ trợ.

Một câu đạt từ 3/4; cần ít nhất 5 câu đạt và không trùng ý.

### Q&A và citation

- Tạo 10 câu có đáp án, gồm ít nhất 2 câu cần tổng hợp nhiều đoạn.
- Tạo 3 câu ngoài phạm vi để kiểm tra từ chối.
- Citation precision mục tiêu ≥90%; 100% câu ngoài phạm vi phải từ chối.

## 5. Hồ sơ bằng chứng

Lưu vào thư mục không chứa dữ liệu nhạy cảm:

```text
evidence/
├── benchmark.json
├── report_demo.json
├── quality_review.md
├── api_samples/
└── demo.mp4
```

Deck chỉ được điền số liệu đã xuất hiện trong hồ sơ này.
