# Antipaper Frontend

React + Vite app shell cho Antipaper: upload tài liệu họp, theo dõi xử lý, xem báo cáo điều hành, mở citation và hỏi đáp tiếng Việt có nguồn.

## Stack

- React 19
- TypeScript
- Vite 7
- React Router 7
- Tailwind CSS v4
- shadcn-style UI primitives
- `lucide-react`

## Chạy local

```bash
npm ci
npm run dev
```

Mở `http://localhost:5173`.

Vite development server chuyển tiếp `/api/v1/*` tới backend tại `http://127.0.0.1:8000`.
Có thể đổi địa chỉ backend trước khi chạy bằng biến môi trường
`ANTIPAPER_BACKEND_URL`.

Khi deploy bản build tĩnh, reverse proxy phải phục vụ SPA và chuyển tiếp `/api/v1/*`
tới FastAPI để giữ nguyên same-origin API contract.

## Kiểm tra

```bash
npm run lint
npm run build
```

`npm run lint` và `npm run build` là các kiểm tra bắt buộc trước khi phát hành.

## Tích hợp API

Frontend gọi API theo hợp đồng tại `../docs/API_CONTRACT.md`, base URL tương đối:

```text
/api/v1
```

Các endpoint đang được dùng:

- `POST /api/v1/documents`
- `GET /api/v1/documents/{document_id}/status`
- `GET /api/v1/documents/{document_id}/report`
- `POST /api/v1/documents/{document_id}/questions`
- `GET /api/v1/documents/{document_id}/pages/{page_number}`
- `GET /api/v1/history`

Lỗi backend được hiển thị đúng trạng thái và không bị che bằng dữ liệu giả.

## Luồng chính

1. Người dùng chọn PDF/DOCX tối đa 25 MB.
2. UI gọi upload API.
3. UI poll status cho tới `completed` hoặc `failed`.
4. Khi hoàn tất, UI lấy report và render summary, thuật ngữ, câu hỏi gợi ý.
5. Người dùng chuyển giữa bốn tab Kết quả: Tổng quan, Thuật ngữ, Câu hỏi phản biện và Văn bản liên quan.
6. Người dùng mở tab Chat cạnh phải thành workspace hỏi đáp cao toàn bộ viewport; vùng này chỉ xuất hiện trong Kết quả đã hoàn tất.
7. Click citation để mở drawer nguồn theo ngữ cảnh.
8. Mở Lịch sử để theo dõi từng tài liệu cùng các lượt xử lý và hỏi đáp.

## File quan trọng

- `src/routes/Workspace.tsx`: sidebar ba mục, upload, bốn tab Kết quả, chat popup, citation drawer và History.
- `src/routes/Landing.tsx`: landing page.
- `src/main.tsx`: root React và hai route `/`, `/app`.
- `src/lib/antipaper-api.ts`: API types, fetch adapter, History và validation.
- `src/components/ui/*`: UI primitives dùng lại trong app.

## Ghi chú phát triển

- File upload chỉ nhận PDF/DOCX, tối đa 25 MB theo API contract.
- Q&A không render citation giả khi backend trả `insufficient_evidence=true`.
- Citation ID phải tồn tại trong `report.citations` mới được hiển thị.
