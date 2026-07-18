# Antipaper — Đọc 60 trang trước cuộc họp trong vài phút

## Vấn đề

Cán bộ thường nhận tài liệu họp 40–60 trang chỉ trước một ngày. Thuật ngữ phức tạp và thiếu thời gian chuẩn bị khiến cuộc họp phải giải thích lại từ đầu, kéo dài và thiếu phản biện.

## Giải pháp

Tải PDF/DOCX lên, Antipaper trả về:

- Tóm tắt: bối cảnh, nội dung chính, điểm cần quyết định, tác động.
- Thuật ngữ/điều khoản quan trọng kèm giải thích ngắn.
- Câu hỏi phản biện và văn bản liên quan cần tham khảo.
- Hỏi đáp tiếng Việt, dẫn đúng trang và mục/điều.

## Điểm khác biệt

Antipaper không chỉ “chat với PDF”. Mỗi kết luận đi cùng bằng chứng; hệ thống không đủ nguồn sẽ từ chối thay vì đoán.

## Luồng demo

```text
Upload tài liệu 40+ trang → Trích xuất cấu trúc → AI xử lý song song
→ Báo cáo cuộc họp → Bấm citation mở đúng nguồn → Hỏi đáp tiếng Việt
```

## Bằng chứng cần điền trước khi nộp

| Chỉ số | Kết quả |
|---|---|
| Tài liệu demo | `[TÊN FILE]` — `[SỐ TRANG]` |
| Thời gian tạo report | `[ĐIỀN SAU BENCHMARK]` |
| Thuật ngữ đúng | `[ĐIỀN]/10` |
| Câu hỏi đạt rubric | `[ĐIỀN]/5` |
| Citation chính xác | `[ĐIỀN]%` |

## Kiến trúc

Next.js → FastAPI → PyMuPDF/DOCX → parser Chương/Mục/Điều → LLM có schema → retrieval in-memory → citation validator.

## Dữ liệu

Văn bản quy phạm pháp luật, Công báo và tài liệu họp công khai từ nguồn chính thức; mỗi file giữ URL, số hiệu, ngày ban hành và trạng thái hiệu lực.

## Lộ trình UBND

1. Demo với văn bản công khai.
2. Pilot tại một đơn vị với SSO, audit log và reviewer.
3. Triển khai on-premise/approved cloud, phân quyền, mã hóa và chính sách lưu trữ.

## Giá trị

Giảm thời gian đọc trước họp, tăng chất lượng câu hỏi và giúp quyết định dựa trên đúng căn cứ trong tài liệu.
