# Giao diện Antipaper

Dashboard Next.js cho luồng upload tài liệu, xem báo cáo, mở citation và hỏi đáp trong cuộc họp.

## Trạng thái

- UI hiện dùng dữ liệu tĩnh trong `app/page.tsx`.
- Chưa kết nối FastAPI và chưa upload file thật.
- Hợp đồng tích hợp nằm tại `../docs/API_CONTRACT.md`.

## Chạy local

```powershell
npm install
npm run dev
```

Mở `http://localhost:3000`.

## Kiểm tra trước khi merge

```powershell
npm run lint
npm run build
```

## Phạm vi 48 giờ

1. Upload PDF/DOCX và hiển thị tiến độ xử lý.
2. Hiển thị bốn phần tóm tắt, thuật ngữ, câu hỏi và văn bản liên quan.
3. Bấm citation để mở đúng trang/mục.
4. Chat tiếng Việt và hiển thị trạng thái từ chối khi thiếu bằng chứng.
5. Có loading, error và retry; không giữ dữ liệu demo hard-code trong luồng chính.
