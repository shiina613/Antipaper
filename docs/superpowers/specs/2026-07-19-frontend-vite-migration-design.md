# Spec: Chuyển frontend Next.js → React + Vite + TypeScript

- Ngày: 2026-07-19
- Phạm vi: thư mục `frontend/`
- Mục tiêu bất biến: **giữ nguyên 100% thiết kế và logic đã có**; migration là tối ưu công nghệ, không được làm mất progress.

## 1. Bối cảnh

`frontend/` hiện là ứng dụng Next.js 16 (App Router) / React 19, Tailwind v4, Base UI. Gồm:

- 2 route: `/` ([app/page.tsx](../../../frontend/app/page.tsx), 310 dòng, landing) và `/app`
  ([app/app/page.tsx](../../../frontend/app/app/page.tsx), 1683 dòng, dashboard).
- Root layout [app/layout.tsx](../../../frontend/app/layout.tsx) nạp 3 font Google qua `next/font`.
- `lib/antipaper-api.ts` (265 dòng, client gọi API), `lib/utils.ts` (`cn`).
- `components/ui/` gồm accordion, badge, button (Base UI + CVA).
- `app/globals.css` (317 dòng, Tailwind v4 `@theme inline` + tokens + animations).
- Proxy API: `next.config.ts` rewrite `/api/v1/*` → `ANTIPAPER_BACKEND_URL` (mặc định `http://127.0.0.1:8000`).

Toàn bộ logic nghiệp vụ và UI **độc lập framework**. Chỉ lớp routing/entry/font/config phụ thuộc Next.js.

## 2. Mục tiêu & phi mục tiêu

**Mục tiêu**
- Chạy trên React + Vite + TypeScript (SPA client-side).
- Bảo toàn nguyên vẹn: giao diện (font, màu, layout, animation), hành vi 2 trang, toàn bộ logic
  trong `lib/` và `components/`.
- Xóa các file chỉ thuộc Next.js sau khi migrate.

**Phi mục tiêu**
- Không SSR/SSG (dashboard vốn là client component).
- Không refactor logic nghiệp vụ, không đổi thiết kế, không nâng cấp thư viện ngoài phần bắt buộc.
- Không sửa backend.

## 3. Nguyên tắc bảo toàn progress

Giữ alias `@/*` → gốc `frontend/` (đúng như `tsconfig.json` hiện tại). Nhờ đó `lib/` và
`components/` **không di chuyển, không sửa import** — mọi `@/lib/...`, `@/components/...` tiếp tục đúng.
Chỉ lớp Next.js (routing, layout, font, config) được thay.

## 4. Cấu trúc thư mục sau migration

```
frontend/
  index.html            # MỚI: entry Vite, <title>+meta (thay Metadata), <div id="root">
  vite.config.ts        # MỚI: plugin react + @tailwindcss/vite, alias @, server.proxy /api/v1
  tsconfig.json         # SỬA: cấu hình bundler, alias @/*; bỏ next
  tsconfig.node.json    # MỚI: cho vite.config.ts
  eslint.config.mjs     # SỬA: cấu hình React + TS tối giản (bỏ eslint-config-next)
  package.json          # SỬA: deps + scripts (xem mục 7)
  components.json       # SỬA: rsc:false
  src/
    main.tsx            # MỚI: createRoot + BrowserRouter + import @fontsource + import './index.css'
    App.tsx             # MỚI: <Routes>: "/"→<Landing/>, "/app"→<Dashboard/>
    pages/
      landing.tsx       # từ app/page.tsx
      dashboard.tsx     # từ app/app/page.tsx
    index.css           # từ app/globals.css + thêm :root font-family variables
  components/ui/*.tsx    # GIỮ NGUYÊN
  lib/*.ts              # GIỮ NGUYÊN
  public/motifs/**      # GIỮ NGUYÊN
  public/favicon.ico    # từ app/favicon.ico
```

## 5. Ánh xạ thay đổi Next.js → Vite

| Next.js | Thay bằng | File ảnh hưởng |
|---|---|---|
| App Router (thư mục `app/`) | `react-router-dom` v7, `BrowserRouter` + 2 `<Route>` | App.tsx (mới) |
| `import Link from "next/link"` | `import { Link } from "react-router-dom"` (prop `href` → `to`) | landing.tsx, dashboard.tsx |
| `import Image from "next/image"` | `<img>` thường, `src="/motifs/..."` | dashboard.tsx |
| `export const metadata` | thẻ trong `index.html` (`<title>Antipaper</title>`, meta description) | index.html |
| `"use client"`, `suppressHydrationWarning` | bỏ | dashboard.tsx |
| `next/font/google` | `@fontsource/*` + `:root` variables (mục 6) | main.tsx, index.css |
| `next.config.ts` rewrites | `server.proxy` trong vite.config.ts (mục 8) | vite.config.ts |
| `@tailwindcss/postcss` + postcss.config.mjs | plugin `@tailwindcss/vite` | vite.config.ts |
| alias `@/*` → `./*` | cùng ánh xạ trong vite.config.ts `resolve.alias` + tsconfig `paths` | vite.config.ts, tsconfig.json |

Ngoài các dòng import ở đầu `landing.tsx`/`dashboard.tsx`, **nội dung JSX/logic của 2 trang giữ nguyên**.

## 6. Font (self-host qua @fontsource)

Cài `@fontsource/be-vietnam-pro`, `@fontsource/space-mono`, `@fontsource/spectral`.

Trong `main.tsx`, import đúng các weight đang dùng:
- Be Vietnam Pro: 400, 500, 600, 700
- Space Mono: 400, 700
- Spectral: 500, 600, 700

Trong `index.css`, định nghĩa `:root` để khớp các biến mà `@theme inline` của globals đang tham chiếu
(`--font-sans: var(--font-be-vietnam-pro)`, `--font-mono: var(--font-space-mono)`,
`--font-display: var(--font-spectral)`):

```css
:root {
  --font-be-vietnam-pro: "Be Vietnam Pro", ui-sans-serif, system-ui, sans-serif;
  --font-space-mono: "Space Mono", ui-monospace, SFMono-Regular, monospace;
  --font-spectral: "Spectral", ui-serif, Georgia, serif;
}
```

`@fontsource` gói unicode-range của các subset (gồm vietnamese) trong file weight, nên glyph tiếng Việt
được phục vụ như bản Next self-host. Không phụ thuộc mạng khi chạy.

## 7. package.json

**Gỡ:** `next`, `eslint-config-next`, `@tailwindcss/postcss`.
**Thêm:** `vite`, `@vitejs/plugin-react`, `@tailwindcss/vite`, `react-router-dom`,
`@fontsource/be-vietnam-pro`, `@fontsource/space-mono`, `@fontsource/spectral`, các eslint plugin React/TS.
**Giữ:** `react`, `react-dom`, `@base-ui/react`, `class-variance-authority`, `clsx`,
`tailwind-merge`, `lucide-react`, `tailwindcss`, `tw-animate-css`, `shadcn`, `typescript`.

Scripts:
```json
"dev": "vite",
"build": "tsc -b && vite build",
"preview": "vite preview",
"lint": "eslint ."
```

## 8. Proxy dev server (vite.config.ts)

```ts
server: {
  proxy: {
    "/api/v1": {
      target: process.env.ANTIPAPER_BACKEND_URL ?? "http://127.0.0.1:8000",
      changeOrigin: true,
    },
  },
}
```

Client tiếp tục gọi relative `/api/v1` → `lib/antipaper-api.ts` không đổi. Với bản build tĩnh, deploy
cần một reverse proxy tương đương (ghi chú trong README, ngoài phạm vi code lần này).

## 9. File bị xóa (thuộc công nghệ không dùng)

`next.config.ts`, `next-env.d.ts`, `postcss.config.mjs`, `app/layout.tsx`, và cả thư mục `app/` sau khi
đã chuyển 2 page + css + favicon; thư mục build `.next/`.

## 10. Kiểm chứng (bằng chứng thực thi, không suy đoán)

1. `npm install` thành công.
2. `npm run build` pass (tsc + vite build không lỗi).
3. `npm run dev`, mở `/` và `/app`: xác nhận font/màu/layout/animation **giống hệt** bản Next, và
   dashboard gọi backend qua proxy trả dữ liệu (cần backend `python -m src` chạy).
4. `npm run lint` sạch.

## 11. Rủi ro đã kiểm soát

- `@import "shadcn/tailwind.css"` và `@import "tw-animate-css"` trong globals: đã xác minh resolve qua
  node_modules (`shadcn` exports `./tailwind.css` → `dist/tailwind.css`) → build được dưới `@tailwindcss/vite`.
- Dashboard là client component thuần (`"use client"`), không dùng server fetch/RSC → chuyển SPA an toàn.
- Alias không đổi ⇒ không phát sinh sửa import trong `lib/`, `components/`.
