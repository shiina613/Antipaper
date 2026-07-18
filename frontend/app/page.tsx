"use client";

import type { LucideIcon } from "lucide-react";
import {
  BookOpenText,
  CircleHelp,
  FileText,
  LoaderCircle,
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
          <TopBar title={activeTitle} apiMode={apiMode} pageCount={report.page_count} status={documentStatus} />
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
