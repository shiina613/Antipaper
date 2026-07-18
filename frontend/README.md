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

Mở `http://localhost:3000`.

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

Nếu backend chưa chạy hoặc API lỗi, adapter trong `lib/antipaper-api.ts` tự fallback sang dữ liệu mock đúng shape contract và UI hiển thị badge `Demo fallback`.

## Luồng chính

1. Người dùng chọn PDF/DOCX tối đa 25 MB.
2. UI gọi upload API.
3. UI poll status cho tới `completed` hoặc `failed`.
4. Khi hoàn tất, UI lấy report và render summary, thuật ngữ, câu hỏi gợi ý.
5. Người dùng hỏi đáp trong chat.
6. Click citation để mở viewer bên phải.

## File quan trọng

- `app/page.tsx`: app shell, upload, processing, report, Q&A, citation viewer.
- `app/layout.tsx`: metadata, font, root layout.
- `lib/antipaper-api.ts`: API types, fetch adapter, validation, mock fallback.
- `components/ui/*`: UI primitives dùng lại trong app.

## Ghi chú phát triển

- Không cần env var cho mock mode; fallback tự động khi API không sẵn sàng.
- File upload chỉ nhận PDF/DOCX, tối đa 25 MB theo API contract.
- Q&A không render citation giả khi backend trả `insufficient_evidence=true`.
- Citation ID phải tồn tại trong `report.citations` mới được hiển thị.
