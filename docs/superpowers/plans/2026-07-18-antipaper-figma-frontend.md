# Antipaper Figma Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current `/` frontend with the full Antipaper Figma app shell, using the API contract first and contract-shaped mock data as fallback.

**Architecture:** Build a small client-side Next.js app shell with a thin API adapter. The adapter owns API calls, error normalization, fallback mock responses, and type definitions; the page owns UI state, polling, upload, Q&A, and citation selection. The root layout stops rendering the old marketing navbar/footer around the app shell.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Tailwind CSS v4, existing shadcn-style UI primitives, `lucide-react`, native `fetch`, native file input.

## Global Constraints

- Replace route `/` with the Antipaper app shell.
- Use API endpoints from `docs/API_CONTRACT.md` first.
- Fall back to contract-shaped mock data on network/backend failure.
- Validate PDF/DOCX upload files up to 25 MB.
- Handle empty, uploading, queued, processing, completed, failed, insufficient-evidence, and citation-loading states.
- Use existing Tailwind v4 and current UI primitives.
- Use `lucide-react` icons instead of downloaded Figma icon assets.
- Do not add new frontend dependencies unless an existing dependency cannot cover a required control.
- Do not add routing unless a screen genuinely needs its own URL; tabs/views inside the app shell are enough for this pass.
- Verify with `npm run lint` and `npm run build` in `frontend/`.

---

## File Structure

- Create `frontend/lib/antipaper-api.ts`: API contract types, mock fixture, adapter functions, fallback metadata, file validation.
- Modify `frontend/app/layout.tsx`: remove global marketing `Navbar` and `Footer`; keep `lang="vi"`, metadata, fonts, and global CSS.
- Replace `frontend/app/page.tsx`: client app shell, layout, navigation, upload, processing, report, Q&A, citation viewer, responsive UI.

No new dependency or test framework is needed. Verification is by TypeScript, ESLint, Next build, and manual browser smoke.

---

### Task 1: API Adapter And Mock Fallback

**Files:**
- Create: `frontend/lib/antipaper-api.ts`

**Interfaces:**
- Produces:
  - `type DocumentStatus = "queued" | "processing" | "completed" | "failed"`
  - `type ProcessingStage = "queued" | "extracting" | "detecting_tables" | "stitching" | "summarizing" | "completed" | "failed"`
  - `type ApiMode = "api" | "mock"`
  - `type ApiResult<T> = T & { apiMode: ApiMode }`
  - `type ReportResponse`
  - `type CitationMeta`
  - `type QuestionResponse`
  - `type PageResponse`
  - `type UploadResponse`
  - `type StatusResponse`
  - `function validateDocumentFile(file: File): string | null`
  - `async function uploadDocument(file: File): Promise<ApiResult<UploadResponse>>`
  - `async function getDocumentStatus(documentId: string): Promise<ApiResult<StatusResponse>>`
  - `async function getDocumentReport(documentId: string): Promise<ApiResult<ReportResponse>>`
  - `async function askDocumentQuestion(documentId: string, question: string): Promise<ApiResult<QuestionResponse>>`
  - `async function getDocumentPage(documentId: string, pageNumber: number): Promise<ApiResult<PageResponse>>`
  - `function citationLabel(citation: CitationMeta): string`
  - `function stageLabel(stage: ProcessingStage | string): string`
- Consumes: none.

- [ ] **Step 1: Create the API adapter**

Add `frontend/lib/antipaper-api.ts`:

```ts
const API_BASE = "/api/v1";
const MAX_FILE_SIZE = 25 * 1024 * 1024;
const SUPPORTED_TYPES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);

export type DocumentStatus = "queued" | "processing" | "completed" | "failed";
export type ProcessingStage =
  | "queued"
  | "extracting"
  | "detecting_tables"
  | "stitching"
  | "summarizing"
  | "completed"
  | "failed";
export type ApiMode = "api" | "mock";
export type ApiResult<T> = T & { apiMode: ApiMode };

export type ApiErrorPayload = {
  error: {
    code: string;
    message: string;
    retryable: boolean;
  };
};

export type UploadResponse = {
  document_id: string;
  status: DocumentStatus;
  cached: boolean;
};

export type StatusResponse = {
  document_id: string;
  status: DocumentStatus;
  stage: ProcessingStage;
  progress: number;
  elapsed_seconds: number;
  error: ApiErrorPayload["error"] | null;
};

export type CitationMeta = {
  page: number;
  chapter: string | null;
  article: string | null;
  clause: string | null;
  excerpt: string;
};

export type CitedText = {
  text: string;
  citation_ids: string[];
};

export type ReportResponse = {
  document_id: string;
  file_name: string;
  page_count: number;
  processing_seconds: number;
  summary: {
    context: CitedText[];
    main_content: CitedText[];
    decision_points: CitedText[];
    impact: CitedText[];
  };
  terms: Array<{
    term: string;
    explanation: string;
    citation_ids: string[];
  }>;
  suggested_questions: Array<{
    question: string;
    rationale: string;
    citation_ids: string[];
  }>;
  related_documents: Array<{
    title: string;
    document_number: string;
    source: string;
    reason: string;
    citation_ids: string[];
  }>;
  citations: Record<string, CitationMeta>;
};

export type QuestionResponse = {
  answer: string;
  insufficient_evidence: boolean;
  citation_ids: string[];
  latency_ms: number;
};

export type PageResponse = {
  document_id: string;
  page_number: number;
  text: string;
  blocks?: Array<{
    id: string;
    text: string;
    citation_id?: string;
  }>;
};

export const mockDocumentId = "mock-antipaper-q3";

export const mockReport: ReportResponse = {
  document_id: mockDocumentId,
  file_name: "Báo cáo Tài chính Q3_2023.pdf",
  page_count: 142,
  processing_seconds: 38.2,
  summary: {
    context: [
      {
        text: "Báo cáo tập trung vào kết quả kinh doanh quý 3, đặc biệt là mảng dịch vụ đám mây và năng lực hạ tầng.",
        citation_ids: ["P12-D7"],
      },
    ],
    main_content: [
      {
        text: "Tổng doanh thu thuần của mảng dịch vụ đám mây trong quý 3 đạt 4.250 tỷ VNĐ.",
        citation_ids: ["P12-D7"],
      },
      {
        text: "Mức tăng trưởng so với cùng kỳ năm 2022 là 37,1%.",
        citation_ids: ["P14-D2"],
      },
    ],
    decision_points: [
      {
        text: "Cần quyết định mức ưu tiên đầu tư tiếp cho hạ tầng IaaS/PaaS ở khu vực phía Nam.",
        citation_ids: ["P14-D2"],
      },
    ],
    impact: [
      {
        text: "Việc mở rộng khách hàng doanh nghiệp lớn làm tăng áp lực vận hành và yêu cầu kiểm soát chi phí.",
        citation_ids: ["P18-D4"],
      },
    ],
  },
  terms: [
    {
      term: "Doanh thu thuần",
      explanation: "Doanh thu sau khi trừ các khoản giảm trừ, dùng để đánh giá hiệu quả kinh doanh thực tế.",
      citation_ids: ["P12-D7"],
    },
    {
      term: "IaaS",
      explanation: "Dịch vụ hạ tầng điện toán đám mây cung cấp máy chủ, lưu trữ và mạng theo nhu cầu.",
      citation_ids: ["P14-D2"],
    },
    {
      term: "PaaS",
      explanation: "Nền tảng đám mây hỗ trợ triển khai ứng dụng mà không cần tự vận hành toàn bộ hạ tầng.",
      citation_ids: ["P14-D2"],
    },
    {
      term: "Biên lợi nhuận gộp",
      explanation: "Tỷ lệ lợi nhuận còn lại sau khi trừ giá vốn, phản ánh hiệu quả cung cấp dịch vụ.",
      citation_ids: ["P18-D4"],
    },
  ],
  suggested_questions: [
    {
      question: "Mức tăng trưởng 37,1% đến từ khách hàng mới hay tăng sử dụng của khách hàng hiện hữu?",
      rationale: "Làm rõ nguồn tăng trưởng trước khi quyết định mở rộng đầu tư.",
      citation_ids: ["P14-D2"],
    },
    {
      question: "Hai trung tâm dữ liệu mới có làm tăng chi phí vận hành trong quý 4 không?",
      rationale: "Kết nối tăng trưởng doanh thu với rủi ro chi phí.",
      citation_ids: ["P18-D4"],
    },
  ],
  related_documents: [
    {
      title: "Kế hoạch đầu tư hạ tầng số 2024",
      document_number: "KH-2024-Cloud",
      source: "cited_in_document",
      reason: "Liên quan đến năng lực mở rộng trung tâm dữ liệu.",
      citation_ids: ["P14-D2"],
    },
  ],
  citations: {
    "P12-D7": {
      page: 12,
      chapter: "Section 3",
      article: "Doanh thu dịch vụ",
      clause: null,
      excerpt: "Tổng doanh thu thuần của mảng dịch vụ đám mây trong Quý 3 năm 2023 đạt 4.250 tỷ VNĐ.",
    },
    "P14-D2": {
      page: 14,
      chapter: "Section 3",
      article: "Phân tích tăng trưởng",
      clause: null,
      excerpt:
        "So với cùng kỳ năm 2022 (đạt 3.100 tỷ VNĐ), mảng này ghi nhận mức tăng trưởng 37.1%, chủ yếu nhờ mở rộng khách hàng doanh nghiệp lớn và triển khai 2 trung tâm dữ liệu mới.",
    },
    "P18-D4": {
      page: 18,
      chapter: "Section 4",
      article: "Chi phí vận hành",
      clause: null,
      excerpt: "Chi phí vận hành tăng nhẹ 5% do lạm phát, tuy nhiên biên lợi nhuận gộp vẫn duy trì ở mức ổn định 42%.",
    },
  },
};

export function validateDocumentFile(file: File): string | null {
  const extension = file.name.toLowerCase().split(".").pop();
  const supportedByExtension = extension === "pdf" || extension === "docx";

  if (!SUPPORTED_TYPES.has(file.type) && !supportedByExtension) {
    return "Chỉ hỗ trợ PDF hoặc DOCX.";
  }

  if (file.size > MAX_FILE_SIZE) {
    return "Tệp vượt quá giới hạn 25 MB.";
  }

  return null;
}

export function citationLabel(citation: CitationMeta): string {
  return `Trang ${citation.page}`;
}

export function stageLabel(stage: ProcessingStage | string): string {
  const labels: Record<string, string> = {
    queued: "Đang xếp hàng",
    extracting: "Trích xuất văn bản",
    detecting_tables: "Nhận diện bảng",
    stitching: "Ghép nội dung",
    summarizing: "Tạo tóm tắt",
    completed: "Hoàn tất",
    failed: "Thất bại",
  };
  return labels[stage] ?? "Đang xử lý";
}

async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<ApiResult<T>> {
  const response = await fetch(input, init);

  if (!response.ok) {
    let message = "Không thể kết nối backend.";
    try {
      const payload = (await response.json()) as ApiErrorPayload;
      message = payload.error?.message ?? message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  return { ...((await response.json()) as T), apiMode: "api" };
}

function withMock<T>(value: T): ApiResult<T> {
  return { ...value, apiMode: "mock" };
}

export async function uploadDocument(file: File): Promise<ApiResult<UploadResponse>> {
  const formData = new FormData();
  formData.append("file", file);

  try {
    return await fetchJson<UploadResponse>(`${API_BASE}/documents`, {
      method: "POST",
      body: formData,
    });
  } catch {
    return withMock({
      document_id: mockDocumentId,
      status: "processing",
      cached: false,
    });
  }
}

export async function getDocumentStatus(documentId: string): Promise<ApiResult<StatusResponse>> {
  try {
    return await fetchJson<StatusResponse>(`${API_BASE}/documents/${documentId}/status`);
  } catch {
    return withMock({
      document_id: mockDocumentId,
      status: "completed",
      stage: "completed",
      progress: 100,
      elapsed_seconds: mockReport.processing_seconds,
      error: null,
    });
  }
}

export async function getDocumentReport(documentId: string): Promise<ApiResult<ReportResponse>> {
  try {
    return await fetchJson<ReportResponse>(`${API_BASE}/documents/${documentId}/report`);
  } catch {
    return withMock(mockReport);
  }
}

export async function askDocumentQuestion(documentId: string, question: string): Promise<ApiResult<QuestionResponse>> {
  try {
    return await fetchJson<QuestionResponse>(`${API_BASE}/documents/${documentId}/questions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    const insufficient = question.toLowerCase().includes("không có trong tài liệu");
    return withMock({
      answer: insufficient
        ? "Tôi không tìm thấy bằng chứng đủ rõ trong tài liệu để trả lời câu hỏi này."
        : "Dựa trên báo cáo, tổng doanh thu thuần của mảng dịch vụ đám mây trong Quý 3 năm 2023 đạt 4.250 tỷ VNĐ và tăng 37,1% so với cùng kỳ năm trước.",
      insufficient_evidence: insufficient,
      citation_ids: insufficient ? [] : ["P12-D7", "P14-D2"],
      latency_ms: 420,
    });
  }
}

export async function getDocumentPage(documentId: string, pageNumber: number): Promise<ApiResult<PageResponse>> {
  try {
    return await fetchJson<PageResponse>(`${API_BASE}/documents/${documentId}/pages/${pageNumber}`);
  } catch {
    const citation = Object.entries(mockReport.citations).find(([, item]) => item.page === pageNumber);
    return withMock({
      document_id: mockDocumentId,
      page_number: pageNumber,
      text:
        citation?.[1].excerpt ??
        "Không có nội dung trang trong mock fallback. Vui lòng kiểm tra lại backend page API.",
      blocks: citation
        ? [
            {
              id: `${citation[0]}-block`,
              text: citation[1].excerpt,
              citation_id: citation[0],
            },
          ]
        : [],
    });
  }
}
```

- [ ] **Step 2: Run lint to catch type/style issues**

Run:

```bash
cd frontend && npm run lint
```

Expected: lint may fail because the new file is not yet consumed or because existing code has unrelated issues, but there should be no syntax parse error in `frontend/lib/antipaper-api.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/antipaper-api.ts
git commit -m "feat: add Antipaper API fallback adapter"
```

---

### Task 2: App Layout And Shell Navigation

**Files:**
- Modify: `frontend/app/layout.tsx`
- Replace: `frontend/app/page.tsx`

**Interfaces:**
- Consumes from Task 1:
  - `ApiMode`
  - `DocumentStatus`
  - `ProcessingStage`
  - `ReportResponse`
  - `StatusResponse`
  - `mockReport`
  - `stageLabel`
- Produces:
  - A client-rendered `/` app shell.
  - `type ViewKey = "upload" | "processing" | "report" | "qa"`
  - `const navItems: Array<{ key: ViewKey; label: string; icon: LucideIcon }>`

- [ ] **Step 1: Remove global marketing chrome**

Replace `frontend/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono, Inter } from "next/font/google";
import { cn } from "@/lib/utils";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Antipaper",
  description: "Executive intelligence dashboard for Vietnamese meeting documents.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className={cn("font-sans", inter.variable)}>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Replace `frontend/app/page.tsx` with the shell scaffold**

Use this scaffold first; later tasks fill the workspaces:

```tsx
"use client";

import type { LucideIcon } from "lucide-react";
import {
  BookOpenText,
  CircleHelp,
  FileText,
  LoaderCircle,
  MessageSquareText,
  Plus,
  Quote,
  SearchCheck,
  Settings,
  Upload,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  type ApiMode,
  type DocumentStatus,
  type ProcessingStage,
  type ReportResponse,
  type StatusResponse,
  mockReport,
  stageLabel,
} from "@/lib/antipaper-api";
import { cn } from "@/lib/utils";

type ViewKey = "upload" | "processing" | "report" | "qa";

const navItems: Array<{ key: ViewKey; label: string; icon: LucideIcon }> = [
  { key: "upload", label: "Tải lên", icon: Upload },
  { key: "processing", label: "Trích xuất", icon: SearchCheck },
  { key: "report", label: "Tóm tắt", icon: BookOpenText },
  { key: "qa", label: "Citation", icon: Quote },
];

const initialStatus: StatusResponse = {
  document_id: mockReport.document_id,
  status: "completed",
  stage: "completed",
  progress: 100,
  elapsed_seconds: mockReport.processing_seconds,
  error: null,
};

export default function Home() {
  const [view, setView] = useState<ViewKey>("qa");
  const [apiMode] = useState<ApiMode>("mock");
  const [documentStatus] = useState<DocumentStatus>("completed");
  const [status] = useState<StatusResponse>(initialStatus);
  const [report] = useState<ReportResponse>(mockReport);

  const activeTitle = useMemo(() => {
    if (view === "upload") return "Tải tài liệu họp";
    if (view === "processing") return stageLabel(status.stage);
    if (view === "report") return "Tóm tắt điều hành";
    return report.file_name;
  }, [report.file_name, status.stage, view]);

  return (
    <main className="min-h-screen bg-[#fafaf4] text-[#1a1c19]">
      <div className="grid min-h-screen lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <SideNav activeView={view} onChange={setView} />
        <section className="flex min-h-screen flex-col border-r border-[#c4c7c7]/70">
          <TopBar
            title={activeTitle}
            apiMode={apiMode}
            pageCount={report.page_count}
            status={documentStatus}
          />
          <div className="flex-1 overflow-auto px-4 py-6 sm:px-6">
            {view === "upload" && <PlaceholderPanel title="Upload workspace" />}
            {view === "processing" && <PlaceholderPanel title="Processing workspace" />}
            {view === "report" && <PlaceholderPanel title="Report workspace" />}
            {view === "qa" && <PlaceholderPanel title="Q&A workspace" />}
          </div>
        </section>
        <aside className="hidden min-h-screen bg-[#fafaf7] lg:block">
          <PlaceholderPanel title="Citation viewer" />
        </aside>
      </div>
    </main>
  );
}

function SideNav({
  activeView,
  onChange,
}: {
  activeView: ViewKey;
  onChange: (view: ViewKey) => void;
}) {
  return (
    <aside className="border-r border-[#c4c7c7] bg-[#eeeee9] px-4 py-5 lg:min-h-screen">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight">Antipaper</h1>
        <p className="mt-1 font-mono text-xs uppercase tracking-[0.18em] text-[#444748]">
          Executive Intelligence
        </p>
      </div>
      <Button className="mb-8 h-10 w-full rounded-lg bg-black text-white hover:bg-black/85">
        <Plus className="size-4" />
        New Document
      </Button>
      <nav className="space-y-1">
        {navItems.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => onChange(item.key)}
            className={cn(
              "flex h-12 w-full items-center gap-3 rounded-lg px-4 text-left text-[#444748] transition",
              activeView === item.key && "bg-[#c4c7c7]/30 font-bold text-black",
            )}
          >
            <item.icon className="size-5" />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="mt-10 space-y-1 lg:fixed lg:bottom-5 lg:w-[248px]">
        <button className="flex h-10 w-full items-center gap-3 rounded-lg px-4 text-[#444748]">
          <Settings className="size-5" />
          <span>Settings</span>
        </button>
        <button className="flex h-10 w-full items-center gap-3 rounded-lg px-4 text-[#444748]">
          <CircleHelp className="size-5" />
          <span>Help</span>
        </button>
      </div>
    </aside>
  );
}

function TopBar({
  title,
  apiMode,
  pageCount,
  status,
}: {
  title: string;
  apiMode: ApiMode;
  pageCount: number;
  status: DocumentStatus;
}) {
  return (
    <header className="sticky top-0 z-10 flex min-h-18 items-center justify-between border-b border-[#c4c7c7]/70 bg-[#fafaf4]/90 px-4 py-3 backdrop-blur sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex size-9 items-center justify-center rounded bg-[#eeeee9]">
          <FileText className="size-5" />
        </div>
        <div className="min-w-0">
          <h2 className="truncate text-xl font-medium tracking-tight sm:text-2xl">{title}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-2 font-mono text-xs text-[#444748]">
            <span className="size-1.5 rounded-full bg-[#566340]" />
            <span>{status === "completed" ? `Đã phân tích ${pageCount} trang` : "Đang xử lý"}</span>
            {apiMode === "mock" && <Badge variant="outline">Demo fallback</Badge>}
          </div>
        </div>
      </div>
      <LoaderCircle className="size-5 text-[#444748]" />
    </header>
  );
}

function PlaceholderPanel({ title }: { title: string }) {
  return (
    <div className="rounded-lg border border-[#c4c7c7] bg-white p-6">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-[#444748]">{title}</p>
    </div>
  );
}
```

- [ ] **Step 3: Run lint**

Run:

```bash
cd frontend && npm run lint
```

Expected: PASS, or only actionable errors in files changed by this task.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/layout.tsx frontend/app/page.tsx
git commit -m "feat: add Antipaper app shell"
```

---

### Task 3: Upload And Processing Flow

**Files:**
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes from Task 1:
  - `validateDocumentFile`
  - `uploadDocument`
  - `getDocumentStatus`
  - `getDocumentReport`
  - `StatusResponse`
  - `ReportResponse`
- Produces:
  - `UploadWorkspace`
  - `ProcessingWorkspace`
  - Live state transitions from upload to processing to completed report.

- [ ] **Step 1: Add imports**

Add these imports to `frontend/app/page.tsx`:

```tsx
import { ChangeEvent, FormEvent, useEffect, useRef } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileUp,
  RefreshCcw,
} from "lucide-react";
import {
  getDocumentReport,
  getDocumentStatus,
  uploadDocument,
  validateDocumentFile,
} from "@/lib/antipaper-api";
```

If this conflicts with the existing React import, collapse it to:

```tsx
import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
```

- [ ] **Step 2: Replace top-level state in `Home`**

Replace the fixed mock state in `Home` with:

```tsx
const [view, setView] = useState<ViewKey>("upload");
const [apiMode, setApiMode] = useState<ApiMode>("mock");
const [documentId, setDocumentId] = useState<string | null>(null);
const [documentStatus, setDocumentStatus] = useState<DocumentStatus>("queued");
const [status, setStatus] = useState<StatusResponse>(initialStatus);
const [report, setReport] = useState<ReportResponse | null>(null);
const [selectedFile, setSelectedFile] = useState<File | null>(null);
const [uploadError, setUploadError] = useState<string | null>(null);
const [isUploading, setIsUploading] = useState(false);
const [isPolling, setIsPolling] = useState(false);
const fileInputRef = useRef<HTMLInputElement | null>(null);

const activeReport = report ?? mockReport;
```

Update `activeTitle` to use `activeReport`:

```tsx
const activeTitle = useMemo(() => {
  if (view === "upload") return "Tải tài liệu họp";
  if (view === "processing") return stageLabel(status.stage);
  if (view === "report") return "Tóm tắt điều hành";
  return activeReport.file_name;
}, [activeReport.file_name, status.stage, view]);
```

- [ ] **Step 3: Add upload handlers inside `Home`**

Add these functions inside `Home`, before `return`:

```tsx
function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
  const file = event.target.files?.[0] ?? null;
  setSelectedFile(file);
  setUploadError(file ? validateDocumentFile(file) : null);
}

async function handleUpload(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  if (!selectedFile) {
    setUploadError("Vui lòng chọn một tệp PDF hoặc DOCX.");
    return;
  }

  const validationError = validateDocumentFile(selectedFile);
  if (validationError) {
    setUploadError(validationError);
    return;
  }

  setIsUploading(true);
  setUploadError(null);
  setView("processing");

  const upload = await uploadDocument(selectedFile);
  setApiMode(upload.apiMode);
  setDocumentId(upload.document_id);
  setDocumentStatus(upload.status);
  setStatus({
    document_id: upload.document_id,
    status: upload.status,
    stage: upload.status === "queued" ? "queued" : "extracting",
    progress: upload.status === "queued" ? 5 : 18,
    elapsed_seconds: 0,
    error: null,
  });
  setIsUploading(false);
  setIsPolling(true);
}

function resetUpload() {
  setView("upload");
  setDocumentId(null);
  setReport(null);
  setSelectedFile(null);
  setUploadError(null);
  setIsUploading(false);
  setIsPolling(false);
  if (fileInputRef.current) fileInputRef.current.value = "";
}
```

- [ ] **Step 4: Add polling effect inside `Home`**

Add this effect after the handlers:

```tsx
useEffect(() => {
  if (!documentId || !isPolling) return;

  let cancelled = false;

  async function tick() {
    const nextStatus = await getDocumentStatus(documentId);
    if (cancelled) return;

    setApiMode(nextStatus.apiMode);
    setStatus(nextStatus);
    setDocumentStatus(nextStatus.status);

    if (nextStatus.status === "completed") {
      const nextReport = await getDocumentReport(documentId);
      if (cancelled) return;
      setApiMode(nextReport.apiMode);
      setReport(nextReport);
      setView("qa");
      setIsPolling(false);
      return;
    }

    if (nextStatus.status === "failed") {
      setIsPolling(false);
    }
  }

  tick();
  const interval = window.setInterval(tick, 1800);

  return () => {
    cancelled = true;
    window.clearInterval(interval);
  };
}, [documentId, isPolling]);
```

- [ ] **Step 5: Replace placeholder upload and processing panels**

Replace these two render branches:

```tsx
{view === "upload" && <PlaceholderPanel title="Upload workspace" />}
{view === "processing" && <PlaceholderPanel title="Processing workspace" />}
```

with:

```tsx
{view === "upload" && (
  <UploadWorkspace
    fileInputRef={fileInputRef}
    selectedFile={selectedFile}
    uploadError={uploadError}
    isUploading={isUploading}
    onFileChange={handleFileChange}
    onSubmit={handleUpload}
  />
)}
{view === "processing" && (
  <ProcessingWorkspace
    status={status}
    apiMode={apiMode}
    onRetry={resetUpload}
  />
)}
```

- [ ] **Step 6: Add `UploadWorkspace` and `ProcessingWorkspace` below `TopBar`**

Add:

```tsx
function UploadWorkspace({
  fileInputRef,
  selectedFile,
  uploadError,
  isUploading,
  onFileChange,
  onSubmit,
}: {
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  selectedFile: File | null;
  uploadError: string | null;
  isUploading: boolean;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <form onSubmit={onSubmit} className="grid gap-6 xl:grid-cols-[minmax(0,500px)_380px]">
      <section>
        <div className="mb-6">
          <h2 className="text-2xl font-medium tracking-tight">Tải tài liệu họp</h2>
          <p className="mt-2 text-[#444748]">Hỗ trợ PDF, DOCX. Tối đa 25MB mỗi tệp.</p>
        </div>
        <label className="flex min-h-[400px] cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-[#c4c7c7] bg-white p-8 text-center shadow-sm">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="sr-only"
            onChange={onFileChange}
          />
          <span className="mb-6 flex size-20 items-center justify-center rounded-full bg-[#eeeee9]">
            <FileUp className="size-9" />
          </span>
          <span className="text-lg font-medium">
            {selectedFile ? selectedFile.name : "Kéo thả tài liệu hoặc chọn từ máy"}
          </span>
          <span className="mt-3 text-sm text-[#444748]">PDF/DOCX, tối đa 25MB</span>
        </label>
        {uploadError && (
          <p className="mt-4 flex items-center gap-2 text-sm text-red-700">
            <AlertTriangle className="size-4" />
            {uploadError}
          </p>
        )}
        <Button
          type="submit"
          disabled={isUploading}
          className="mt-6 h-10 rounded-lg bg-black px-6 text-white hover:bg-black/85"
        >
          {isUploading ? "Đang tải..." : "Bắt đầu phân tích"}
        </Button>
      </section>
      <aside className="rounded-lg border border-[#c4c7c7] bg-white p-6">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-[#444748]">Mục tiêu phân tích</p>
        <div className="mt-6 space-y-5">
          <UploadGoal title="Tóm tắt điều hành" description="Rút ra bối cảnh, nội dung chính, quyết định và tác động." />
          <UploadGoal title="Hỏi đáp có nguồn" description="Mỗi câu trả lời cần citation để kiểm chứng nhanh." />
        </div>
      </aside>
    </form>
  );
}

function UploadGoal({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex gap-3">
      <CheckCircle2 className="mt-1 size-5 text-[#566340]" />
      <div>
        <h3 className="font-medium">{title}</h3>
        <p className="mt-1 text-sm leading-6 text-[#444748]">{description}</p>
      </div>
    </div>
  );
}

function ProcessingWorkspace({
  status,
  apiMode,
  onRetry,
}: {
  status: StatusResponse;
  apiMode: ApiMode;
  onRetry: () => void;
}) {
  const steps: ProcessingStage[] = ["extracting", "detecting_tables", "stitching", "summarizing"];

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <section className="flex min-h-[560px] flex-col items-center justify-center rounded-lg bg-[#fafaf4] p-8 text-center">
        <div className="relative flex size-48 items-center justify-center rounded-full border-8 border-[#d3e3b7] bg-white">
          <span className="text-4xl font-semibold">{status.progress}%</span>
        </div>
        <h2 className="mt-8 text-2xl font-medium">{stageLabel(status.stage)}</h2>
        <p className="mt-3 max-w-md text-[#444748]">
          {status.status === "failed"
            ? status.error?.message ?? "Quá trình xử lý thất bại."
            : "Đang trích xuất, nhận diện bảng và tạo intelligence report."}
        </p>
        <div className="mt-6 flex items-center gap-3 font-mono text-xs text-[#444748]">
          <Clock3 className="size-4" />
          <span>{status.elapsed_seconds.toFixed(1)}s</span>
          {apiMode === "mock" && <Badge variant="outline">Demo fallback</Badge>}
        </div>
        {status.status === "failed" && (
          <Button type="button" variant="outline" className="mt-6 rounded-lg" onClick={onRetry}>
            <RefreshCcw className="size-4" />
            Thử lại
          </Button>
        )}
      </section>
      <aside className="rounded-lg border border-[#c4c7c7] bg-white p-6">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-[#444748]">Pipeline status</p>
        <div className="mt-6 space-y-4">
          {steps.map((step) => (
            <div key={step} className="flex items-center gap-3">
              <span
                className={cn(
                  "size-3 rounded-full border border-[#c4c7c7]",
                  status.progress >= stepProgress(step) && "border-[#566340] bg-[#566340]",
                )}
              />
              <span className="text-sm">{stageLabel(step)}</span>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}

function stepProgress(stage: ProcessingStage) {
  const progress: Record<ProcessingStage, number> = {
    queued: 0,
    extracting: 15,
    detecting_tables: 35,
    stitching: 55,
    summarizing: 75,
    completed: 100,
    failed: 100,
  };
  return progress[stage];
}
```

- [ ] **Step 7: Run build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: wire upload and processing flow"
```

---

### Task 4: Report And Citation Viewer

**Files:**
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes from Task 1:
  - `citationLabel`
  - `getDocumentPage`
  - `CitationMeta`
  - `PageResponse`
  - `ReportResponse`
- Produces:
  - `ReportWorkspace`
  - `CitationViewer`
  - Citation click behavior with page/excerpt fallback.

- [ ] **Step 1: Add imports**

Add:

```tsx
import {
  citationLabel,
  getDocumentPage,
  type CitationMeta,
  type PageResponse,
} from "@/lib/antipaper-api";
import { ExternalLink } from "lucide-react";
```

Merge with existing imports instead of duplicating module imports.

- [ ] **Step 2: Add citation state inside `Home`**

Add:

```tsx
const [selectedCitationId, setSelectedCitationId] = useState<string>("P14-D2");
const [selectedPage, setSelectedPage] = useState<PageResponse | null>(null);
const [isCitationLoading, setIsCitationLoading] = useState(false);
const selectedCitation = activeReport.citations[selectedCitationId] ?? null;
```

Add this handler:

```tsx
async function handleSelectCitation(citationId: string) {
  const citation = activeReport.citations[citationId];
  if (!citation) return;

  setSelectedCitationId(citationId);
  setIsCitationLoading(true);
  const page = await getDocumentPage(activeReport.document_id, citation.page);
  setApiMode(page.apiMode);
  setSelectedPage(page);
  setIsCitationLoading(false);
}
```

- [ ] **Step 3: Replace report placeholder and citation aside**

Replace:

```tsx
{view === "report" && <PlaceholderPanel title="Report workspace" />}
```

with:

```tsx
{view === "report" && (
  <ReportWorkspace report={activeReport} onSelectCitation={handleSelectCitation} />
)}
```

Replace the citation aside body with:

```tsx
<CitationViewer
  report={activeReport}
  citationId={selectedCitationId}
  citation={selectedCitation}
  page={selectedPage}
  isLoading={isCitationLoading}
/>
```

Add a mobile citation panel below the center content:

```tsx
<div className="mt-6 lg:hidden">
  <CitationViewer
    report={activeReport}
    citationId={selectedCitationId}
    citation={selectedCitation}
    page={selectedPage}
    isLoading={isCitationLoading}
  />
</div>
```

- [ ] **Step 4: Add report/citation components**

Add:

```tsx
function ReportWorkspace({
  report,
  onSelectCitation,
}: {
  report: ReportResponse;
  onSelectCitation: (citationId: string) => void;
}) {
  const sections = [
    ["Bối cảnh", report.summary.context],
    ["Nội dung chính", report.summary.main_content],
    ["Điểm cần quyết định", report.summary.decision_points],
    ["Tác động", report.summary.impact],
  ] as const;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-2">
        {sections.map(([title, items]) => (
          <div key={title} className="rounded-lg border border-[#c4c7c7] bg-white p-5">
            <h3 className="font-medium">{title}</h3>
            <div className="mt-4 space-y-4">
              {items.map((item) => (
                <CitedParagraph key={item.text} item={item} report={report} onSelectCitation={onSelectCitation} />
              ))}
            </div>
          </div>
        ))}
      </section>
      <section className="rounded-lg border border-[#c4c7c7] bg-white p-5">
        <h3 className="font-medium">Thuật ngữ</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {report.terms.map((term) => (
            <div key={term.term} className="rounded-lg border border-[#c4c7c7]/70 p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Badge>{term.term}</Badge>
                {term.citation_ids.map((id) => (
                  <CitationButton
                    key={id}
                    citationId={id}
                    report={report}
                    onSelectCitation={onSelectCitation}
                  />
                ))}
              </div>
              <p className="text-sm leading-6 text-[#444748]">{term.explanation}</p>
            </div>
          ))}
        </div>
      </section>
      <section className="rounded-lg border border-[#c4c7c7] bg-white p-5">
        <h3 className="font-medium">Câu hỏi gợi ý</h3>
        <div className="mt-4 space-y-3">
          {report.suggested_questions.map((question) => (
            <div key={question.question} className="rounded-lg border border-[#c4c7c7]/70 p-4">
              <p className="font-medium">{question.question}</p>
              <p className="mt-2 text-sm leading-6 text-[#444748]">{question.rationale}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {question.citation_ids.map((id) => (
                  <CitationButton
                    key={id}
                    citationId={id}
                    report={report}
                    onSelectCitation={onSelectCitation}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function CitedParagraph({
  item,
  report,
  onSelectCitation,
}: {
  item: { text: string; citation_ids: string[] };
  report: ReportResponse;
  onSelectCitation: (citationId: string) => void;
}) {
  return (
    <div>
      <p className="text-sm leading-6 text-[#1a1c19]">{item.text}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {item.citation_ids.map((id) => (
          <CitationButton key={id} citationId={id} report={report} onSelectCitation={onSelectCitation} />
        ))}
      </div>
    </div>
  );
}

function CitationButton({
  citationId,
  report,
  onSelectCitation,
}: {
  citationId: string;
  report: ReportResponse;
  onSelectCitation: (citationId: string) => void;
}) {
  const citation = report.citations[citationId];
  if (!citation) return null;

  return (
    <button
      type="button"
      onClick={() => onSelectCitation(citationId)}
      className="rounded-full bg-[#566340] px-2.5 py-1 font-mono text-[11px] text-white"
    >
      {citationLabel(citation)}
    </button>
  );
}

function CitationViewer({
  report,
  citationId,
  citation,
  page,
  isLoading,
}: {
  report: ReportResponse;
  citationId: string;
  citation: CitationMeta | null;
  page: PageResponse | null;
  isLoading: boolean;
}) {
  return (
    <div className="min-h-full border-l border-[#c4c7c7] bg-[#fafaf7]">
      <header className="flex h-18 items-center justify-between border-b border-[#c4c7c7]/70 px-5">
        <div className="flex items-center gap-2 font-semibold">
          <Quote className="size-4" />
          Nguồn trích dẫn
        </div>
      </header>
      <div className="space-y-6 p-5">
        {!citation ? (
          <p className="text-sm text-[#444748]">Chọn một citation để xem nguồn.</p>
        ) : (
          <>
            <div>
              <Badge variant="outline" className="rounded-sm font-mono uppercase">
                {citationLabel(citation)}
              </Badge>
              <h3 className="mt-4 text-lg font-medium">{report.file_name}</h3>
              <p className="mt-2 font-mono text-xs leading-5 text-[#444748]">
                {[citation.chapter, citation.article, citation.clause].filter(Boolean).join(" / ")}
              </p>
            </div>
            <div className="rounded-lg border border-[#c4c7c7] bg-white p-5 shadow-sm">
              {isLoading ? (
                <p className="text-sm text-[#444748]">Đang tải citation...</p>
              ) : (
                <p className="whitespace-pre-line text-sm leading-7 text-[#444748]">
                  {page?.text ?? citation.excerpt}
                </p>
              )}
            </div>
            <Button type="button" variant="outline" className="w-full rounded-none">
              <ExternalLink className="size-4" />
              Mở toàn tài liệu
            </Button>
            <p className="font-mono text-[11px] text-[#444748]">Citation ID: {citationId}</p>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run lint/build**

Run:

```bash
cd frontend && npm run lint && npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: render report and citations"
```

---

### Task 5: Q&A Workspace And Final Verification

**Files:**
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes from Task 1:
  - `askDocumentQuestion`
  - `QuestionResponse`
- Produces:
  - `QaWorkspace`
  - Disabled Q&A before completed report
  - Insufficient-evidence rendering without fake citations
  - Final responsive app.

- [ ] **Step 1: Add imports**

Add:

```tsx
import { SendHorizontal, ThumbsDown, ThumbsUp, Copy } from "lucide-react";
import { askDocumentQuestion, type QuestionResponse } from "@/lib/antipaper-api";
```

Merge imports from the same modules.

- [ ] **Step 2: Add chat types and initial messages**

Add above `Home`:

```tsx
type ChatMessage =
  | {
      role: "user";
      text: string;
    }
  | {
      role: "assistant";
      text: string;
      insufficientEvidence: boolean;
      citationIds: string[];
      latencyMs: number;
    };

const initialMessages: ChatMessage[] = [
  {
    role: "user",
    text: "Tổng doanh thu thuần của mảng dịch vụ đám mây trong quý 3 là bao nhiêu, và có sự tăng trưởng nào so với cùng kỳ năm ngoái không?",
  },
  {
    role: "assistant",
    text: "Dựa trên báo cáo, tổng doanh thu thuần của mảng dịch vụ đám mây trong Quý 3 năm 2023 đạt 4.250 tỷ VNĐ. So với cùng kỳ năm 2022, mảng này ghi nhận mức tăng trưởng 37,1%.",
    insufficientEvidence: false,
    citationIds: ["P12-D7", "P14-D2"],
    latencyMs: 420,
  },
];
```

- [ ] **Step 3: Add Q&A state and submit handler inside `Home`**

Add:

```tsx
const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
const [question, setQuestion] = useState("");
const [isAsking, setIsAsking] = useState(false);
const canAsk = Boolean(report ?? activeReport);
```

Add handler:

```tsx
async function handleAskQuestion(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  const trimmed = question.trim();
  if (!trimmed || !canAsk || isAsking) return;

  setQuestion("");
  setIsAsking(true);
  setMessages((current) => [...current, { role: "user", text: trimmed }]);

  const response: QuestionResponse & { apiMode: ApiMode } = await askDocumentQuestion(
    activeReport.document_id,
    trimmed,
  );
  setApiMode(response.apiMode);
  setMessages((current) => [
    ...current,
    {
      role: "assistant",
      text: response.answer,
      insufficientEvidence: response.insufficient_evidence,
      citationIds: response.citation_ids,
      latencyMs: response.latency_ms,
    },
  ]);
  setIsAsking(false);
}
```

- [ ] **Step 4: Replace Q&A placeholder**

Replace:

```tsx
{view === "qa" && <PlaceholderPanel title="Q&A workspace" />}
```

with:

```tsx
{view === "qa" && (
  <QaWorkspace
    report={activeReport}
    messages={messages}
    question={question}
    canAsk={canAsk}
    isAsking={isAsking}
    onQuestionChange={setQuestion}
    onSubmit={handleAskQuestion}
    onSelectCitation={handleSelectCitation}
  />
)}
```

- [ ] **Step 5: Add `QaWorkspace`**

Add:

```tsx
function QaWorkspace({
  report,
  messages,
  question,
  canAsk,
  isAsking,
  onQuestionChange,
  onSubmit,
  onSelectCitation,
}: {
  report: ReportResponse;
  messages: ChatMessage[];
  question: string;
  canAsk: boolean;
  isAsking: boolean;
  onQuestionChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onSelectCitation: (citationId: string) => void;
}) {
  return (
    <div className="mx-auto flex min-h-[calc(100vh-130px)] max-w-3xl flex-col">
      <div className="flex-1 space-y-8 pb-32">
        <div className="flex justify-center">
          <span className="rounded-full bg-[#f4f4ee] px-3 py-1 font-mono text-xs text-[#444748]">
            Hôm nay, 09:41
          </span>
        </div>
        {messages.map((message, index) =>
          message.role === "user" ? (
            <div key={`${message.role}-${index}`} className="flex justify-end">
              <div className="max-w-[486px] rounded-bl-xl rounded-br-xl rounded-tl-xl rounded-tr-sm bg-[#e8e8e3] px-6 py-4">
                <p className="leading-7">{message.text}</p>
              </div>
            </div>
          ) : (
            <div key={`${message.role}-${index}`} className="space-y-2">
              <p className="flex items-center gap-2 pl-1 font-mono text-xs font-semibold uppercase tracking-[0.12em] text-[#444748]">
                <MessageSquareText className="size-4" />
                Antipaper AI
              </p>
              <div className="max-w-[560px] rounded-bl-xl rounded-br-xl rounded-tl-sm rounded-tr-xl border border-[#c4c7c7] bg-white px-6 py-5 shadow-sm">
                <p className="leading-7">{message.text}</p>
                {!message.insufficientEvidence && message.citationIds.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {message.citationIds.map((id) => (
                      <CitationButton key={id} citationId={id} report={report} onSelectCitation={onSelectCitation} />
                    ))}
                  </div>
                )}
                {message.insufficientEvidence && (
                  <Badge variant="outline" className="mt-4">
                    Không đủ bằng chứng
                  </Badge>
                )}
              </div>
              <div className="flex gap-2 pl-1 text-[#444748]">
                <button type="button" aria-label="Sao chép câu trả lời" className="p-1">
                  <Copy className="size-4" />
                </button>
                <button type="button" aria-label="Hữu ích" className="p-1">
                  <ThumbsUp className="size-4" />
                </button>
                <button type="button" aria-label="Không hữu ích" className="p-1">
                  <ThumbsDown className="size-4" />
                </button>
              </div>
            </div>
          ),
        )}
      </div>
      <form onSubmit={onSubmit} className="sticky bottom-0 bg-gradient-to-t from-[#fafaf4] via-[#fafaf4] to-transparent pb-6 pt-10">
        <div className="flex items-end rounded-lg border border-[#c4c7c7] bg-white p-2 shadow-sm">
          <textarea
            value={question}
            onChange={(event) => onQuestionChange(event.target.value)}
            disabled={!canAsk || isAsking}
            rows={1}
            placeholder="Đặt câu hỏi về tài liệu..."
            className="min-h-12 flex-1 resize-none rounded-md border-0 bg-transparent px-3 py-3 outline-none"
          />
          <Button
            type="submit"
            disabled={!canAsk || isAsking || question.trim().length === 0}
            className="h-11 rounded-md bg-[#d3e3b7] text-black hover:bg-[#c7d9a8]"
            aria-label="Gửi câu hỏi"
          >
            <SendHorizontal className="size-5" />
          </Button>
        </div>
        <p className="mt-3 text-center font-mono text-[11px] text-[#444748]/70">
          AI có thể cung cấp thông tin không chính xác. Hãy kiểm chứng nguồn trích dẫn.
        </p>
      </form>
    </div>
  );
}
```

- [ ] **Step 6: Remove unused placeholder**

Delete `PlaceholderPanel` if no render branch still uses it.

- [ ] **Step 7: Run final verification**

Run:

```bash
cd frontend && npm run lint && npm run build
```

Expected: PASS.

- [ ] **Step 8: Start dev server and inspect**

Run:

```bash
cd frontend && npm run dev
```

Expected: Next.js dev server starts and prints a local URL, usually `http://localhost:3000`.

Open the URL and verify:

- `/` shows Antipaper shell.
- Upload validates unsupported files.
- A valid PDF/DOCX enters processing and falls back to demo when backend is absent.
- Report view renders summary, terms, and suggested questions.
- Q&A renders the Figma-like chat and can submit a question.
- Citation buttons update the citation viewer.
- Mobile width does not overlap text or panels.

- [ ] **Step 9: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: add Antipaper Q&A workspace"
```

---

## Self-Review

Spec coverage:

- Full Figma app shell: Task 2, Task 4, Task 5.
- API-first behavior: Task 1, Task 3, Task 5.
- Mock fallback: Task 1 and all consumers show `apiMode`.
- Upload validation: Task 1 and Task 3.
- Processing states: Task 3.
- Report/glossary/questions: Task 4.
- Citation viewer and citation loading: Task 4.
- Q&A and insufficient evidence: Task 5.
- Responsive behavior: Task 2 layout plus Task 5 final browser inspection.
- Verification: each task has lint/build where relevant; final task has lint/build/dev smoke.

Placeholder scan:

- No `TBD`.
- No `TODO`.
- No "fill in details".
- No "implement later".

Type consistency:

- `ApiResult<T>` is defined in Task 1 and consumed as object spread with `apiMode`.
- `ReportResponse`, `StatusResponse`, `QuestionResponse`, `PageResponse`, and `CitationMeta` are defined in Task 1 before use.
- `handleSelectCitation` is introduced in Task 4 before `QaWorkspace` consumes it in Task 5.
