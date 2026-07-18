# Antipaper Frontend

Next.js app shell cho Antipaper: upload tài liệu họp, theo dõi xử lý, xem báo cáo điều hành, mở citation và hỏi đáp tiếng Việt có nguồn.

## Stack

- Next.js 16 App Router
- React 19
- TypeScript
- Tailwind CSS v4
- shadcn-style UI primitives
- `lucide-react`

## Chạy local

```bash
npm ci
npm run dev
```

Copy `.env.local.example` to `.env.local` when needed. `BACKEND_URL` defaults
to `http://127.0.0.1:8000`; Next proxies browser-relative `/api/*` requests to
that backend. Set `NEXT_PUBLIC_ENABLE_MOCK_FALLBACK=true` only for explicit
demo mode. Default `false` surfaces upload/status/report/page/Q&A errors and
stops polling without silently substituting mock data.

Mở `http://localhost:3000`.

Mặc định Next.js chuyển tiếp `/api/v1/*` tới backend tại `http://127.0.0.1:8000`.
Có thể đổi địa chỉ backend trước khi chạy bằng biến môi trường server-side
`ANTIPAPER_BACKEND_URL`.

## Kiểm tra

```bash
npm run lint
npm run build
```

Hiện `npm run lint` có thể báo 1 warning cũ ở `components/ui/hero-video-dialog.tsx` do dùng thẻ `<img>`.

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

Mock mode locks each uploaded document to one mode, preventing mixed API/mock state.
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

- `app/page.tsx`: sidebar ba mục, upload, bốn tab Kết quả, chat popup, citation drawer và History.
- `app/layout.tsx`: metadata, font, root layout.
- `lib/antipaper-api.ts`: API types, fetch adapter, History và validation.
- `components/ui/*`: UI primitives dùng lại trong app.

## Ghi chú phát triển

- Mock mode requires `NEXT_PUBLIC_ENABLE_MOCK_FALLBACK=true`.
- File upload chỉ nhận PDF/DOCX, tối đa 25 MB theo API contract.
- Q&A không render citation giả khi backend trả `insufficient_evidence=true`.
- Citation ID phải tồn tại trong `report.citations` mới được hiển thị.
