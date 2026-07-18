"use client";

import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  BookOpenText,
  CheckCircle2,
  CircleHelp,
  Clock3,
  ExternalLink,
  FileText,
  FileUp,
  LoaderCircle,
  Plus,
  Quote,
  RefreshCcw,
  SearchCheck,
  Settings,
  Upload,
} from "lucide-react";
import { type ChangeEvent, type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  type ApiMode,
  type DocumentStatus,
  type ProcessingStage,
  type ReportResponse,
  type StatusResponse,
  citationLabel,
  getDocumentReport,
  getDocumentPage,
  getDocumentStatus,
  mockReport,
  stageLabel,
  type CitationMeta,
  type PageResponse,
  uploadDocument,
  validateDocumentFile,
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
  const [selectedCitationId, setSelectedCitationId] = useState<string>("P14-D2");
  const [selectedPage, setSelectedPage] = useState<PageResponse | null>(null);
  const [isCitationLoading, setIsCitationLoading] = useState(false);
  const selectedCitation = activeReport.citations[selectedCitationId] ?? null;

  const activeTitle = useMemo(() => {
    if (view === "upload") return "Tải tài liệu họp";
    if (view === "processing") return stageLabel(status.stage);
    if (view === "report") return "Tóm tắt điều hành";
    return activeReport.file_name;
  }, [activeReport.file_name, status.stage, view]);

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

  useEffect(() => {
    if (!documentId || !isPolling) return;

    let cancelled = false;
    const currentDocumentId = documentId;

    async function tick() {
      const nextStatus = await getDocumentStatus(currentDocumentId);
      if (cancelled) return;

      setApiMode(nextStatus.apiMode);
      setStatus(nextStatus);
      setDocumentStatus(nextStatus.status);

      if (nextStatus.status === "completed") {
        const nextReport = await getDocumentReport(currentDocumentId);
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

  return (
    <main className="min-h-screen bg-[#fafaf4] text-[#1a1c19]">
      <div className="grid min-h-screen lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <SideNav activeView={view} onChange={setView} />
        <section className="flex min-h-screen flex-col border-r border-[#c4c7c7]/70">
          <TopBar
            title={activeTitle}
            apiMode={apiMode}
            pageCount={activeReport.page_count}
            status={documentStatus}
          />
          <div className="flex-1 overflow-auto px-4 py-6 sm:px-6">
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
              <ProcessingWorkspace status={status} apiMode={apiMode} onRetry={resetUpload} />
            )}
            {view === "report" && (
              <ReportWorkspace report={activeReport} onSelectCitation={handleSelectCitation} />
            )}
            {view === "qa" && <PlaceholderPanel title="Q&A workspace" />}
            <div className="mt-6 lg:hidden">
              <CitationViewer
                report={activeReport}
                citationId={selectedCitationId}
                citation={selectedCitation}
                page={selectedPage}
                isLoading={isCitationLoading}
              />
            </div>
          </div>
        </section>
        <aside className="hidden min-h-screen bg-[#fafaf7] lg:block">
          <CitationViewer
            report={activeReport}
            citationId={selectedCitationId}
            citation={selectedCitation}
            page={selectedPage}
            isLoading={isCitationLoading}
          />
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
                  <CitationButton key={id} citationId={id} report={report} onSelectCitation={onSelectCitation} />
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
                  <CitationButton key={id} citationId={id} report={report} onSelectCitation={onSelectCitation} />
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

function PlaceholderPanel({ title }: { title: string }) {
  return (
    <div className="rounded-lg border border-[#c4c7c7] bg-white p-6">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-[#444748]">{title}</p>
    </div>
  );
}
