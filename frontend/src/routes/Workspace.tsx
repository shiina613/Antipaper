import { Link } from "react-router-dom";
import {
  AlertTriangle,
  BookOpenText,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Copy,
  FileQuestion,
  FileText,
  FileUp,
  History as HistoryIcon,
  LayoutDashboard,
  LibraryBig,
  LoaderCircle,
  Menu,
  MessageSquareText,
  MessagesSquare,
  Quote,
  RefreshCcw,
  SendHorizontal,
  Tags,
  Trash2,
  X,
} from "lucide-react";
import { type ChangeEvent, type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import {
  type CitationMeta,
  type DocumentStatus,
  type PageResponse,
  type ProcessingStage,
  type ReportResponse,
  type StatusResponse,
  type TaskHistoryItem,
  type TaskHistoryPage,
  type TaskType,
  askDocumentQuestion,
  ApiRequestError,
  citationLabel,
  deleteHistorySession,
  deleteTaskHistory,
  getDocumentPage,
  getDocumentReport,
  getDocumentStatus,
  getTaskHistory,
  stageLabel,
  uploadDocument,
  validateDocumentFile,
} from "@/lib/antipaper-api";
import { cn } from "@/lib/utils";

type AppView = "upload" | "document" | "history";
type DocumentTab = "overview" | "terms" | "questions" | "related";

type ChatMessage =
  | { role: "user"; text: string }
  | {
      role: "assistant";
      text: string;
      insufficientEvidence: boolean;
      citationIds: string[];
      latencyMs: number;
    };

const emptyHistory: TaskHistoryPage = { items: [], total: 0, limit: 20, offset: 0 };
const ACTIVE_DOCUMENT_STORAGE_KEY = "antipaper.active-document-id";

export default function Home() {
  const [view, setView] = useState<AppView>("upload");
  const [documentTab, setDocumentTab] = useState<DocumentTab>("overview");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [documentStatus, setDocumentStatus] = useState<DocumentStatus | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [documentError, setDocumentError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [selectedCitationIds, setSelectedCitationIds] = useState<string[]>([]);
  const [selectedPages, setSelectedPages] = useState<Record<number, PageResponse>>({});
  const [selectedSourceKind, setSelectedSourceKind] = useState<"summary" | "citation">("citation");
  const [isCitationLoading, setIsCitationLoading] = useState(false);
  const [citationError, setCitationError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [isAsking, setIsAsking] = useState(false);
  const [qaError, setQaError] = useState<string | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);

  const [historyPage, setHistoryPage] = useState<TaskHistoryPage>(emptyHistory);
  const [historyStatus, setHistoryStatus] = useState<DocumentStatus | "">("");
  const [historyType, setHistoryType] = useState<TaskType | "">("");
  const [historyOffset, setHistoryOffset] = useState(0);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyReloadKey, setHistoryReloadKey] = useState(0);
  const [deletingHistoryKey, setDeletingHistoryKey] = useState<string | null>(null);

  const canAsk = documentStatus === "completed" && Boolean(report);

  function resetUpload() {
    setView("upload");
    setDocumentTab("overview");
    setDocumentId(null);
    setDocumentStatus(null);
    setStatus(null);
    setReport(null);
    setSelectedFile(null);
    setUploadError(null);
    setDocumentError(null);
    setIsUploading(false);
    setIsPolling(false);
    setMessages([]);
    setIsChatOpen(false);
    setIsMobileNavOpen(false);
    closeCitation();
    persistActiveDocument(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function closeCitation() {
    setSelectedCitationIds([]);
    setSelectedPages({});
    setSelectedSourceKind("citation");
    setCitationError(null);
  }

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
    setDocumentError(null);
    try {
      const upload = await uploadDocument(selectedFile);
      setDocumentId(upload.document_id);
      persistActiveDocument(upload.document_id);
      setDocumentStatus(upload.status);
      const initialStage: ProcessingStage =
        upload.status === "completed"
          ? "completed"
          : upload.status === "failed"
            ? "failed"
            : upload.status === "queued"
              ? "queued"
              : "parsing";
      const initialProgress =
        upload.status === "completed" || upload.status === "failed"
          ? 100
          : upload.status === "queued"
            ? 0
            : 10;
      setStatus({
        document_id: upload.document_id,
        status: upload.status,
        stage: initialStage,
        progress: initialProgress,
        elapsed_seconds: 0,
        error: null,
      });
      setView("document");
      setDocumentTab("overview");
      setIsPolling(true);
    } catch (error) {
      setUploadError(errorMessage(error, "Không thể tải tài liệu. Vui lòng kiểm tra kết nối backend."));
    } finally {
      setIsUploading(false);
    }
  }

  async function handleSelectCitations(
    citationIds: string[],
    sourceKind: "summary" | "citation" = "summary",
  ) {
    if (!report) return;
    const validIds = Array.from(new Set(citationIds)).filter((id) => Boolean(report.citations[id]));
    if (!validIds.length) return;
    const pageNumbers = Array.from(
      new Set(validIds.map((id) => report.citations[id].page)),
    ).sort((left, right) => left - right);

    setSelectedCitationIds(validIds);
    setSelectedSourceKind(sourceKind);
    setIsChatOpen(false);
    setSelectedPages({});
    setCitationError(null);
    setIsCitationLoading(true);
    const results = await Promise.allSettled(
      pageNumbers.map((pageNumber) => getDocumentPage(report.document_id, pageNumber)),
    );
    const loadedPages: Record<number, PageResponse> = {};
    let failedPages = 0;
    results.forEach((result, index) => {
      if (result.status === "fulfilled") {
        loadedPages[pageNumbers[index]] = result.value;
      } else {
        failedPages += 1;
      }
    });
    setSelectedPages(loadedPages);
    if (failedPages) {
      setCitationError(`Không tải được ${failedPages}/${pageNumbers.length} trang nguồn.`);
    }
    setIsCitationLoading(false);
  }

  async function handleSelectCitation(citationId: string) {
    await handleSelectCitations([citationId], "citation");
  }

  async function handleAskQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || !canAsk || isAsking || !report) return;

    setQuestion("");
    setQaError(null);
    setIsAsking(true);
    setMessages((current) => [...current, { role: "user", text: trimmed }]);
    try {
      const response = await askDocumentQuestion(report.document_id, trimmed);
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
    } catch (error) {
      setQaError(errorMessage(error, "Không thể gửi câu hỏi. Vui lòng thử lại."));
    } finally {
      setIsAsking(false);
    }
  }

  function useSuggestedQuestion(value: string) {
    setQuestion(value);
    setIsChatOpen(true);
  }

  async function openHistoryDocument(item: TaskHistoryItem) {
    if (!item.document_id || item.status !== "completed") return;
    setHistoryError(null);
    setDocumentError(null);
    try {
      const nextReport = await getDocumentReport(item.document_id);
      setDocumentId(item.document_id);
      persistActiveDocument(item.document_id);
      setDocumentStatus("completed");
      setStatus({
        document_id: item.document_id,
        status: "completed",
        stage: "completed",
        progress: 100,
        elapsed_seconds: item.duration_seconds ?? nextReport.processing_seconds,
        error: null,
      });
      setReport(nextReport);
      setDocumentTab("overview");
      setView("document");
      setMessages([]);
      setIsChatOpen(false);
      closeCitation();
    } catch (error) {
      setHistoryError(errorMessage(error, "Không thể mở lại báo cáo này."));
    }
  }

  useEffect(() => {
    const restoredDocumentId = readActiveDocument();
    if (!restoredDocumentId) return;
    const restoreTimer = window.setTimeout(() => {
      setDocumentId(restoredDocumentId);
      setDocumentStatus("queued");
      setStatus({
        document_id: restoredDocumentId,
        status: "queued",
        stage: "queued",
        progress: 0,
        elapsed_seconds: 0,
        error: null,
      });
      setView("document");
      setIsPolling(true);
    }, 0);
    return () => window.clearTimeout(restoreTimer);
  }, []);

  useEffect(() => {
    if (!documentId || !isPolling) return;
    let cancelled = false;
    const currentDocumentId = documentId;

    async function tick() {
      try {
        const nextStatus = await getDocumentStatus(currentDocumentId);
        if (cancelled) return;
        setStatus(nextStatus);
        setDocumentStatus(nextStatus.status);

        if (nextStatus.status === "completed") {
          const nextReport = await getDocumentReport(currentDocumentId);
          if (cancelled) return;
          setReport(nextReport);
          setDocumentTab("overview");
          setIsPolling(false);
        } else if (nextStatus.status === "failed") {
          setIsPolling(false);
        }
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiRequestError && error.status === 404) {
          persistActiveDocument(null);
          setDocumentId(null);
          setDocumentStatus("failed");
          setStatus({
            document_id: currentDocumentId,
            status: "failed",
            stage: "failed",
            progress: 100,
            elapsed_seconds: 0,
            error: {
              code: "DOCUMENT_EXPIRED",
              message: "Backend đã khởi động lại nên tài liệu tạm trong bộ nhớ không còn. Hãy tải lại tài liệu.",
              retryable: false,
            },
          });
          setDocumentError("Backend đã khởi động lại nên tài liệu này không còn. Hãy tải lại tài liệu để phân tích lại.");
          setIsPolling(false);
          return;
        }
        setDocumentError(errorMessage(error, "Mất kết nối khi theo dõi tiến độ xử lý."));
        setIsPolling(false);
      }
    }

    void tick();
    const interval = window.setInterval(() => void tick(), 2_000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [documentId, isPolling]);

  useEffect(() => {
    if (!report || report.enrichment_status !== "pending") return;
    let cancelled = false;
    const startedAt = Date.now();
    let timer: number | undefined;
    const refresh = async () => {
      try {
        const nextReport = await getDocumentReport(report.document_id);
        if (cancelled) return;
        setReport(nextReport);
        if (nextReport.enrichment_status === "pending" && Date.now() - startedAt < 30_000) {
          timer = window.setTimeout(() => void refresh(), 2_000);
        }
      } catch {
        // Related-document enrichment never invalidates the ready report.
      }
    };
    timer = window.setTimeout(() => void refresh(), 2_000);
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [report]);

  useEffect(() => {
    if (view !== "history") return;
    let cancelled = false;

    async function loadHistory() {
      setIsHistoryLoading(true);
      setHistoryError(null);
      try {
        const page = await getTaskHistory({
          limit: 20,
          offset: historyOffset,
          status: historyStatus,
          taskType: historyType,
        });
        if (cancelled) return;
        setHistoryPage(page);
      } catch (error) {
        if (cancelled) return;
        setHistoryError(errorMessage(error, "Không thể tải lịch sử tác vụ."));
      } finally {
        if (!cancelled) setIsHistoryLoading(false);
      }
    }

    void loadHistory();
    return () => {
      cancelled = true;
    };
  }, [historyOffset, historyReloadKey, historyStatus, historyType, view]);

  async function handleDeleteHistorySession(session: HistorySession) {
    const taskCount = session.tasks.length;
    const confirmed = window.confirm(
      `Xóa ${taskCount} mục lịch sử của phiên “${session.title}”? Thao tác này chỉ xóa lịch sử, không xóa tài liệu hoặc báo cáo đang mở.`,
    );
    if (!confirmed) return;

    setDeletingHistoryKey(session.key);
    setHistoryError(null);
    try {
      if (session.documentId) {
        await deleteHistorySession(session.documentId);
      } else {
        await deleteTaskHistory(session.tasks[0].task_id);
      }
      if (historyPage.items.length === taskCount && historyOffset > 0) {
        setHistoryOffset((offset) => Math.max(0, offset - 20));
      }
      setHistoryReloadKey((value) => value + 1);
    } catch (error) {
      setHistoryError(errorMessage(error, "Không thể xóa lịch sử phiên."));
    } finally {
      setDeletingHistoryKey(null);
    }
  }

  return (
    <main className="flex min-h-screen bg-[#f5f1e6] text-[#1b2a44]">
      {isMobileNavOpen && (
        <button
          type="button"
          aria-label="Đóng điều hướng"
          className="fixed inset-0 z-40 bg-black/35 lg:hidden"
          onClick={() => setIsMobileNavOpen(false)}
        />
      )}
      <AppSidebar
        view={view}
        hasDocument={Boolean(documentId)}
        documentName={report?.file_name ?? selectedFile?.name ?? null}
        collapsed={isSidebarCollapsed}
        mobileOpen={isMobileNavOpen}
        onToggleCollapsed={() => setIsSidebarCollapsed((value) => !value)}
        onCloseMobile={() => setIsMobileNavOpen(false)}
        onUpload={resetUpload}
        onResults={() => {
          setView("document");
          setDocumentTab("overview");
          setIsChatOpen(false);
          setIsMobileNavOpen(false);
        }}
        onHistory={() => {
          setView("history");
          setIsChatOpen(false);
          setIsMobileNavOpen(false);
        }}
      />

      <section
        className={cn(
          "relative min-w-0 flex-1 transition-[padding] duration-200",
          view === "document" && report && documentStatus === "completed" && isChatOpen && "2xl:pr-[430px]",
        )}
      >
        <MotifBackdrop />
        <div className="relative z-10">
        <MobileWorkspaceHeader view={view} onOpenMenu={() => setIsMobileNavOpen(true)} />
        {view === "upload" && (
          <PageContainer>
            <UploadWorkspace
              fileInputRef={fileInputRef}
              selectedFile={selectedFile}
              uploadError={uploadError}
              isUploading={isUploading}
              onFileChange={handleFileChange}
              onSubmit={handleUpload}
            />
          </PageContainer>
        )}

        {view === "document" && (
          <>
            {report && documentStatus === "completed" ? (
              <>
                <DocumentHeader report={report} selectedFile={selectedFile} status={status} />
                <PageContainer className="pb-0 pt-5">
                  <ResultTabs activeTab={documentTab} report={report} onChange={setDocumentTab} />
                </PageContainer>
                <PageContainer className="py-7">
                  {documentTab === "overview" && (
                    <OverviewTab report={report} onSelectSources={handleSelectCitations} />
                  )}
                  {documentTab === "terms" && (
                    <TermsTab report={report} onSelectCitation={handleSelectCitation} />
                  )}
                  {documentTab === "questions" && (
                    <QuestionsTab
                      report={report}
                      onSelectCitation={handleSelectCitation}
                      onUseQuestion={useSuggestedQuestion}
                    />
                  )}
                  {documentTab === "related" && (
                    <RelatedTab report={report} onSelectCitation={handleSelectCitation} />
                  )}
                </PageContainer>
              </>
            ) : (
              <PageContainer className="py-10 lg:mx-0 lg:max-w-[970px] lg:px-[90px] lg:py-12">
                <ProcessingDocumentHeader selectedFile={selectedFile} />
                <ProcessingWorkspace
                  status={status}
                  error={documentError}
                  onRetry={() => setIsPolling(true)}
                  onNewDocument={resetUpload}
                />
              </PageContainer>
            )}
          </>
        )}

        {view === "history" && (
          <PageContainer className="py-8">
            <HistoryWorkspace
              page={historyPage}
              statusFilter={historyStatus}
              typeFilter={historyType}
              isLoading={isHistoryLoading}
              error={historyError}
              onStatusFilter={(value) => {
                setHistoryStatus(value);
                setHistoryOffset(0);
              }}
              onTypeFilter={(value) => {
                setHistoryType(value);
                setHistoryOffset(0);
              }}
              onRetry={() => setHistoryReloadKey((value) => value + 1)}
              onOpenDocument={openHistoryDocument}
              onDeleteSession={handleDeleteHistorySession}
              deletingSessionKey={deletingHistoryKey}
              onPrevious={() => setHistoryOffset((value) => Math.max(0, value - 20))}
              onNext={() => setHistoryOffset((value) => value + 20)}
            />
          </PageContainer>
        )}
        </div>
      </section>

      {view === "document" && report && documentStatus === "completed" && (
        <ChatPopup
          open={isChatOpen}
          report={report}
          messages={messages}
          question={question}
          canAsk={canAsk}
          isAsking={isAsking}
          error={qaError}
          onOpen={() => setIsChatOpen(true)}
          onClose={() => setIsChatOpen(false)}
          onQuestionChange={setQuestion}
          onSubmit={handleAskQuestion}
          onSelectCitation={handleSelectCitation}
        />
      )}

      {report && selectedCitationIds.length > 0 && (
        <CitationDrawer
          report={report}
          citationIds={selectedCitationIds}
          pages={selectedPages}
          sourceKind={selectedSourceKind}
          isLoading={isCitationLoading}
          error={citationError}
          onClose={closeCitation}
        />
      )}
    </main>
  );
}

function AppSidebar({
  view,
  hasDocument,
  documentName,
  collapsed,
  mobileOpen,
  onToggleCollapsed,
  onCloseMobile,
  onUpload,
  onResults,
  onHistory,
}: {
  view: AppView;
  hasDocument: boolean;
  documentName: string | null;
  collapsed: boolean;
  mobileOpen: boolean;
  onToggleCollapsed: () => void;
  onCloseMobile: () => void;
  onUpload: () => void;
  onResults: () => void;
  onHistory: () => void;
}) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-50 flex w-[280px] shrink-0 -translate-x-full flex-col border-r border-[#d3c9b2]/60 bg-[#ebe4d3] px-3 py-4 shadow-xl transition-[width,transform] duration-200 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 lg:shadow-none",
        mobileOpen && "translate-x-0",
        collapsed ? "lg:w-[76px]" : "lg:w-[280px]",
      )}
    >
      <div className="flex h-14 items-center justify-between px-3">
        <Link to="/" className="flex min-w-0 items-center gap-2.5 text-left" title="Về trang giới thiệu" aria-label="Về trang giới thiệu">
          <span className="seal size-8 shrink-0 bg-[#faf6ec] font-mono text-[9px] font-bold tracking-tight">AP</span>
          <span className={cn("block truncate text-2xl font-bold tracking-[-0.02em]", collapsed && "lg:hidden")}>Antipaper</span>
        </Link>
        <Button type="button" variant="ghost" size="icon" className="lg:hidden" onClick={onCloseMobile} aria-label="Đóng menu"><X className="size-5" /></Button>
      </div>

      <nav aria-label="Điều hướng chính" className="mt-8 space-y-2">
        <SidebarItem active={view === "upload"} collapsed={collapsed} icon={FileUp} label="Tải lên" onClick={onUpload} />
        <SidebarItem active={view === "document"} collapsed={collapsed} icon={LayoutDashboard} label="Kết quả" onClick={onResults} disabled={!hasDocument} />
        <SidebarItem active={view === "history"} collapsed={collapsed} icon={HistoryIcon} label="Lịch sử" onClick={onHistory} />
      </nav>

      {/* Vùng trống: bấm để thu gọn / mở rộng thanh điều hướng (desktop) */}
      <button
        type="button"
        onClick={onToggleCollapsed}
        aria-label={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}
        title={collapsed ? "Bấm để mở rộng" : "Bấm vùng trống để thu gọn"}
        className="mt-2 min-h-16 flex-1 rounded-lg transition hover:bg-[#d3c9b2]/15 lg:cursor-pointer"
      />

      {documentName && (
        <button type="button" onClick={onResults} title={documentName} className={cn("w-full rounded-lg border border-[#d3c9b2]/70 bg-white/70 p-3 text-left", collapsed && "lg:flex lg:justify-center lg:p-2")}>
          <FileText className="size-4 shrink-0" />
          <span className={cn("mt-2 block truncate text-xs text-[#54606f]", collapsed && "lg:hidden")}>{documentName}</span>
        </button>
      )}
    </aside>
  );
}

function SidebarItem({
  active,
  icon: Icon,
  label,
  collapsed,
  disabled,
  onClick,
}: {
  active: boolean;
  icon: typeof FileUp;
  label: string;
  collapsed: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      title={disabled ? "Hãy tải tài liệu trước" : collapsed ? label : undefined}
      className={cn(
        "flex h-12 w-full items-center gap-3 rounded-lg px-4 text-sm font-medium text-[#3f4a5c] transition hover:bg-[#d3c9b2]/20 focus-visible:outline-2 focus-visible:outline-offset-2",
        active && "bg-[#d3c9b2]/30 font-bold text-black hover:bg-[#d3c9b2]/30",
        collapsed && "lg:justify-center lg:px-0",
        disabled && "cursor-not-allowed opacity-40",
      )}
    >
      <Icon className="size-5 shrink-0" />
      <span className={cn(collapsed && "lg:hidden")}>{label}</span>
    </button>
  );
}

function MobileWorkspaceHeader({ view, onOpenMenu }: { view: AppView; onOpenMenu: () => void }) {
  const title = view === "upload" ? "Tải lên" : view === "document" ? "Kết quả" : "Lịch sử";
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-[#d8cfb8] bg-[#faf6ec]/95 px-4 backdrop-blur lg:hidden">
      <Button type="button" variant="ghost" size="icon" onClick={onOpenMenu} aria-label="Mở điều hướng"><Menu className="size-5" /></Button>
      <span className="font-semibold">{title}</span>
    </header>
  );
}

function PageContainer({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-[1180px] px-4 py-10 sm:px-6", className)}>{children}</div>;
}

function DocumentHeader({
  report,
  selectedFile,
  status,
}: {
  report: ReportResponse | null;
  selectedFile: File | null;
  status: StatusResponse | null;
}) {
  const title = report?.file_name ?? selectedFile?.name ?? "Tài liệu đang xử lý";
  return (
    <section className="border-b border-t-2 border-[#d8cfb8] border-t-[#9c6b1e]/70 bg-white">
      <div className="mx-auto flex max-w-[1180px] flex-col gap-4 px-4 py-6 sm:px-6 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[#5c6675]">Tài liệu hiện tại</p>
          <h1 title={title} className="mt-2 truncate text-2xl font-semibold tracking-tight sm:text-3xl">
            {title}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-[#5c6675]">
            <StatusBadge status={status?.status ?? "queued"} />
            {report && <span>{report.page_count} trang</span>}
            {status && <span>{status.elapsed_seconds.toFixed(1)} giây</span>}
            {report?.generation_mode === "llm" && <Badge variant="outline">Báo cáo AI có kiểm tra nguồn</Badge>}
          </div>
        </div>
        {report && (
          <div className="grid grid-cols-3 gap-5 text-right text-sm">
            <Metric value={report.terms.length} label="Thuật ngữ" />
            <Metric value={report.suggested_questions.length} label="Câu hỏi" />
            <Metric value={Object.keys(report.citations).length} label="Nguồn" />
          </div>
        )}
      </div>
    </section>
  );
}

function ProcessingDocumentHeader({ selectedFile }: { selectedFile: File | null }) {
  return (
    <header>
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#9199a6]">Đang xử lý</p>
      <h1 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-[#1b2a44] sm:text-[40px] sm:leading-none">
        Phân tích tài liệu
      </h1>
      <p className="mt-4 truncate text-base text-[#4a5568] sm:text-lg" title={selectedFile?.name}>
        {selectedFile?.name ?? "Tài liệu đang xử lý"}
      </p>
    </header>
  );
}

function Metric({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <strong className="block text-xl text-[#1b2a44]">{value}</strong>
      <span className="text-xs text-[#5c6675]">{label}</span>
    </div>
  );
}

function ResultTabs({
  activeTab,
  report,
  onChange,
}: {
  activeTab: DocumentTab;
  report: ReportResponse;
  onChange: (tab: DocumentTab) => void;
}) {
  const tabs: Array<{ key: DocumentTab; label: string; description: string; icon: typeof LayoutDashboard; count: number }> = [
    {
      key: "overview",
      label: "Tổng quan",
      description: "Điểm quyết định và tác động",
      icon: LayoutDashboard,
      count: Object.values(report.summary).flat().length,
    },
    {
      key: "terms",
      label: "Thuật ngữ",
      description: "Điều khoản cần làm rõ",
      icon: Tags,
      count: report.terms.length,
    },
    {
      key: "questions",
      label: "Câu hỏi phản biện",
      description: "Câu hỏi dùng trong cuộc họp",
      icon: MessagesSquare,
      count: report.suggested_questions.length,
    },
    {
      key: "related",
      label: "Văn bản liên quan",
      description: "Căn cứ được tài liệu nhắc đến",
      icon: LibraryBig,
      count: report.related_documents.length,
    },
  ];

  return (
    <div role="tablist" aria-label="Các nhóm kết quả" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          role="tab"
          aria-selected={activeTab === tab.key}
          onClick={() => onChange(tab.key)}
          className={cn(
            "flex min-h-24 items-start gap-3 rounded-lg border border-[#d8cfb8] bg-white p-4 text-left transition hover:border-[#7b8494] hover:shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2",
            activeTab === tab.key && "border-black bg-white shadow-sm",
          )}
        >
          <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-lg bg-[#efe7d5]", activeTab === tab.key && "bg-[#e6ddca]")}>
            <tab.icon className="size-4" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex items-center justify-between gap-2 font-semibold">
              <span>{tab.label}</span>
              <span className="rounded-full bg-[#e6ddca] px-2 py-0.5 font-mono text-[10px]">{tab.count}</span>
            </span>
            <span className="mt-1 block text-xs leading-5 text-[#5c6675]">{tab.description}</span>
          </span>
        </button>
      ))}
    </div>
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
    <div className="space-y-10 pt-6 sm:pt-8">
      <header className="max-w-2xl">


      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
        <form onSubmit={onSubmit}>
          <label className="group relative flex min-h-[300px] cursor-pointer flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed border-[#c3b998] bg-white/85 p-8 text-center shadow-[0_18px_40px_-28px_rgba(27,42,68,0.4)] backdrop-blur-sm transition hover:border-[#a5271f] hover:bg-white">
            <span className="pointer-events-none absolute -right-8 -top-8 size-40 rounded-full bg-[#efe4c8]/50 blur-2xl" />
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="sr-only"
              onChange={onFileChange}
            />
            <span className="relative mb-5 flex size-16 items-center justify-center rounded-full bg-[#efe4c8] text-[#996515] transition group-hover:scale-105 group-hover:bg-[#a5271f] group-hover:text-white">
              <FileUp className="size-7" />
            </span>
            <span className="relative max-w-full truncate text-lg font-medium">
              {selectedFile ? selectedFile.name : "Kéo thả tài liệu hoặc chọn từ máy"}
            </span>
            <span className="relative mt-2 text-sm text-[#5c6675]">PDF/DOCX, tối đa 25 MB</span>
          </label>
          {uploadError && <InlineError className="mt-4" message={uploadError} />}
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <Button type="submit" disabled={isUploading} className="h-11 bg-[#a5271f] px-6 text-white hover:bg-[#7f1c16]">
              {isUploading ? <LoaderCircle className="size-4 animate-spin" /> : <FileUp className="size-4" />}
              {isUploading ? "Đang tải tài liệu" : "Bắt đầu phân tích"}
            </Button>

          </div>
        </form>
        <aside className="rounded-2xl border border-[#d8cfb8] bg-white/85 p-6 backdrop-blur-sm">
          <h2 className="font-semibold">Bạn sẽ nhận được</h2>
          <div className="mt-5 space-y-5">
            <UploadGoal title="Báo cáo điều hành" description="Bối cảnh, nội dung chính, điểm cần quyết định và tác động." />
            <UploadGoal title="Câu hỏi phản biện" description="Các câu hỏi cần đặt trong cuộc họp, kèm lý do và căn cứ." />
            <UploadGoal title="Kiểm chứng một thao tác" description="Mỗi nhận định quan trọng mở đúng trang và đoạn nguồn." />
          </div>
          <div className="mt-6 border-t border-[#e2dac6] pt-5 text-xs leading-5 text-[#5c6675]">
            Chỉ tải tài liệu công khai hoặc đã được phê duyệt cho môi trường demo.
          </div>
        </aside>
      </div>

      <div>
        <div className="rule-brass max-w-full" />
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <UploadStep n="01" icon={FileUp} title="Tải tài liệu" description="PDF/DOCX 40–60 trang, công khai hoặc đã được phê duyệt." />
          <UploadStep n="02" icon={LayoutDashboard} title="Phân tích dưới 60 giây" description="Bóc tách theo trang/điều, tổng hợp báo cáo, thuật ngữ và câu hỏi." />
          <UploadStep n="03" icon={Quote} title="Kiểm chứng & hỏi đáp" description="Mở đúng đoạn nguồn; hỏi đáp tiếng Việt dẫn đúng trang và mục/điều." />
        </div>
      </div>
    </div>
  );
}

function UploadStep({
  n,
  icon: Icon,
  title,
  description,
}: {
  n: string;
  icon: typeof FileUp;
  title: string;
  description: string;
}) {
  return (
    <article className="group relative overflow-hidden rounded-2xl border border-[#d8cfb8] bg-white/70 p-5 backdrop-blur-sm transition hover:border-[#996515]/60 hover:bg-white">
      <span className="absolute right-4 top-3 font-mono text-2xl font-bold text-[#efe4c8] transition group-hover:text-[#f0e0bf]">{n}</span>
      <span className="flex size-10 items-center justify-center rounded-xl bg-[#1b2a44] text-[#f5f1e6] transition group-hover:bg-[#a5271f]">
        <Icon className="size-4" />
      </span>
      <h3 className="mt-4 font-semibold text-[#1b2a44]">{title}</h3>
      <p className="mt-1.5 text-sm leading-6 text-[#54606f]">{description}</p>
    </article>
  );
}

function MotifBackdrop() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* Trống đồng Đông Sơn — góc trên phải, quay rất chậm */}
      <div
        className="motif-spin-slow absolute -right-28 -top-28 size-[460px] bg-contain bg-center bg-no-repeat opacity-[0.32] sm:-right-20"
        style={{ backgroundImage: "url('/motifs/drum.png')" }}
      />
      {/* Trống đồng nhỏ — góc dưới phải, mờ hơn để cân bằng bố cục */}
      <div
        className="motif-spin-slow absolute -bottom-24 -right-16 size-[250px] bg-contain bg-center bg-no-repeat opacity-[0.13]"
        style={{ backgroundImage: "url('/motifs/drum.png')", animationDirection: "reverse" }}
      />
      {/* Hoa sen — dưới bên trái, chân sen sát mép dưới màn hình */}
      <div
        className="absolute -bottom-10 left-0 h-[480px] w-[440px] bg-contain bg-bottom bg-no-repeat opacity-[0.36] sm:left-6"
        style={{ backgroundImage: "url('/motifs/lotus.png')" }}
      />
    </div>
  );
}

function UploadGoal({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex gap-3">
      <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-[#996515]" />
      <div>
        <h3 className="text-sm font-medium">{title}</h3>
        <p className="mt-1 text-sm leading-6 text-[#5c6675]">{description}</p>
      </div>
    </div>
  );
}

function ProcessingWorkspace({
  status,
  error,
  onRetry,
  onNewDocument,
}: {
  status: StatusResponse | null;
  error: string | null;
  onRetry: () => void;
  onNewDocument: () => void;
}) {
  if (!status) {
    return <EmptyState title="Chưa có tác vụ xử lý" description="Hãy tải một tài liệu để bắt đầu." actionLabel="Tải tài liệu" onAction={onNewDocument} />;
  }

  const failed = status.status === "failed";
  const progress = Math.min(100, Math.max(0, Math.round(status.progress)));
  const currentStepIndex = processingStepIndex(status);
  const currentStep = processingSteps[currentStepIndex];

  return (
    <section
      aria-live="polite"
      aria-busy={!failed && status.status !== "completed"}
      className="mt-9 rounded-xl border border-[#d8cfb8] bg-white p-6 shadow-[0_3px_14px_rgba(28,37,34,0.08)] sm:p-8"
    >
      <div className="flex items-center justify-between gap-5">
        <h2 className={cn("text-lg font-semibold text-[#1b2a44]", failed && "text-red-800")}>
          {failed ? "Không thể xử lý tài liệu" : currentStep.label}
        </h2>
        <span className="shrink-0 font-mono text-base text-[#4a5568]">{progress}%</span>
      </div>

      <div
        role="progressbar"
        aria-label="Tiến độ phân tích tài liệu"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        className="mt-4 h-2.5 overflow-hidden rounded-full bg-[#e2dac6]"
      >
        <div
          className={cn("h-full rounded-full bg-[#256b52] transition-[width] duration-500 ease-out", failed && "bg-red-700")}
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-2 font-mono text-xs text-[#4a5568]">
        <span>
          Trạng thái: <strong className="font-bold text-[#26344d]">{status.status}</strong>
        </span>
        <span>Đã trôi qua: {status.elapsed_seconds.toFixed(1)}s</span>
      </div>

      <ol className="mt-10 space-y-6" aria-label="Các bước phân tích tài liệu">
        {processingSteps.map((step, index) => {
          const completed = !failed && (status.status === "completed" || index < currentStepIndex);
          const active = !failed && status.status !== "completed" && index === currentStepIndex;
          return (
            <li key={step.id} className="flex min-h-7 items-center gap-4">
              <span
                className={cn(
                  "relative flex size-7 shrink-0 items-center justify-center rounded-full border-2 border-[#cfc5ac] bg-white text-white",
                  completed && "border-[#256b52] bg-[#256b52]",
                  active && "border-[#256b52] shadow-[0_0_0_3px_rgba(23,98,79,0.12)]",
                  failed && index === currentStepIndex && "border-red-700",
                )}
                aria-hidden="true"
              >
                {completed && <CheckCircle2 className="size-4" strokeWidth={3} />}
                {active && <span className="size-2.5 rounded-full bg-[#256b52]" />}
                {failed && index === currentStepIndex && <X className="size-4 text-red-700" strokeWidth={3} />}
              </span>
              <span
                className={cn(
                  "text-base text-[#9199a6] sm:text-lg",
                  (completed || active) && "text-[#26344d]",
                  active && "font-semibold text-[#1b2a44]",
                  failed && index === currentStepIndex && "font-semibold text-red-800",
                )}
              >
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>

      {(failed || error) && (
        <div className="mt-8 border-t border-[#e2dac6] pt-5">
          <InlineError message={error ?? status.error?.message ?? "Quá trình xử lý đã thất bại."} />
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={onRetry}>
              <RefreshCcw className="size-4" /> Theo dõi lại
            </Button>
            <Button type="button" onClick={onNewDocument}>Tải tài liệu khác</Button>
          </div>
        </div>
      )}
    </section>
  );
}

const processingSteps = [
  { id: "queued", label: "Đưa vào hàng đợi" },
  { id: "extracting", label: "Bóc tách văn bản & metadata" },
  { id: "indexing", label: "Lập chỉ mục theo trang/điều" },
  { id: "reporting", label: "Tổng hợp & sinh báo cáo" },
  { id: "completed", label: "Hoàn tất" },
] as const;

function processingStepIndex(status: StatusResponse) {
  const stageSteps: Partial<Record<ProcessingStage, number>> = {
    queued: 0,
    parsing: 1,
    extracting: 1,
    detecting_tables: 1,
    stitching: 2,
    generating: 3,
    summarizing: 3,
    ready: 4,
    completed: 4,
    failed: 3,
  };
  const mappedStep = stageSteps[status.stage];
  if (mappedStep !== undefined) return mappedStep;
  if (status.progress >= 100) return 4;
  if (status.progress >= 60) return 3;
  if (status.progress >= 35) return 2;
  if (status.progress >= 10) return 1;
  return 0;
}

function OverviewTab({
  report,
  onSelectSources,
}: {
  report: ReportResponse;
  onSelectSources: (citationIds: string[]) => void;
}) {
  const sections = [
    ["Điểm cần quyết định", "Các nội dung cần chủ trì kết luận hoặc lựa chọn phương án.", report.summary.decision_points],
    ["Bối cảnh", "Phạm vi và lý do tài liệu được trình tại cuộc họp.", report.summary.context],
    ["Nội dung chính", "Những luận điểm và số liệu cốt lõi cần nắm.", report.summary.main_content],
    ["Tác động", "Hệ quả, trách nhiệm hoặc rủi ro cần lưu ý.", report.summary.impact],
  ] as const;
  return (
    <div className="mx-auto max-w-[900px]">
      <article className="mt-7 space-y-8 rounded-lg border border-[#d8cfb8] bg-white p-6 shadow-sm md:p-8">
        {sections.map(([title, description, items], index) => (
          <section key={title} className={cn(index === 0 && "rounded-lg border border-[#e6ddca] border-l-4 border-l-[#a5271f] bg-[#f6eeda] p-5")}>
            <h2 className="font-mono text-base font-bold uppercase leading-6 tracking-[0.12em] text-[#3f4a5c]">{title}</h2>
            <p className="mt-2 text-sm text-[#5c6675]">{description}</p>
            <SummarySectionContent items={items} report={report} onSelectSources={onSelectSources} />
          </section>
        ))}
      </article>
    </div>
  );
}

type ReportTabProps = { report: ReportResponse; onSelectCitation: (citationId: string) => void };

function TermsTab({ report, onSelectCitation }: ReportTabProps) {
  return (
    <div className="mx-auto max-w-[900px]">
      {report.terms.length < 10 && <InlineNotice className="mt-5" message={`Báo cáo hiện có ${report.terms.length}/10 thuật ngữ theo ngưỡng mục tiêu.`} />}
      <div className="mt-7 grid gap-4 md:grid-cols-2">
        {report.terms.map((term) => (
          <article key={term.term} className="rounded-lg border border-[#d8cfb8] bg-white p-6 transition-shadow hover:shadow-sm">
            <h2 className="font-semibold">{term.term}</h2>
            <p className="mt-3 text-sm leading-7 text-[#54606f]">{term.explanation}</p>
            <CitationButtonList ids={term.citation_ids} report={report} onSelectCitation={onSelectCitation} />
          </article>
        ))}
      </div>
    </div>
  );
}

function QuestionsTab({
  report,
  onSelectCitation,
  onUseQuestion,
}: ReportTabProps & { onUseQuestion: (question: string) => void }) {
  return (
    <div className="mx-auto max-w-[900px]">
      {report.suggested_questions.length < 5 && <InlineNotice className="mt-5" message={`Báo cáo hiện có ${report.suggested_questions.length}/5 câu hỏi theo ngưỡng mục tiêu.`} />}
      <div className="mt-7 space-y-4">
        {report.suggested_questions.map((item, index) => (
          <article key={item.question} className="relative overflow-hidden rounded-lg border border-[#d8cfb8] bg-white p-5 transition-colors hover:border-[#7b8494] sm:p-6">
            <span className={cn("absolute inset-y-0 left-0 w-1", index % 2 === 0 ? "bg-[#1b2a44]" : "bg-[#996515]")} />
            <div className="pl-2">
              <div className="min-w-0 flex-1">
                <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-[#7b8494]">Câu hỏi {index + 1}</p>
                <h2 className="font-medium leading-7">{item.question}</h2>
                <p className="mt-2 text-sm leading-6 text-[#5c6675]"><strong>Lý do:</strong> {item.rationale}</p>
                <CitationButtonList ids={item.citation_ids} report={report} onSelectCitation={onSelectCitation} />
                <Button type="button" variant="outline" className="mt-4" onClick={() => onUseQuestion(item.question)}>
                  <MessageSquareText className="size-4" /> Dùng câu hỏi này
                </Button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function RelatedTab({ report, onSelectCitation }: ReportTabProps) {
  return (
    <div className="mx-auto max-w-[1100px] py-7">

      {report.related_documents.length ? (
        <Accordion className="mt-7 gap-3" multiple>
          {report.related_documents.map((item) => (
            <AccordionItem key={`${item.document_number}-${item.title}`} value={`${item.document_number}-${item.title}`} className="overflow-hidden rounded-xl border border-[#d8cfb8] bg-white shadow-sm">
              <AccordionTrigger className="rounded-none px-5 py-4 text-base font-medium hover:bg-[#f3ecdb] hover:no-underline sm:px-6">
                <span>{item.title}{item.document_number ? ` (${item.document_number})` : ""}</span>
              </AccordionTrigger>
              <AccordionContent className="border-t border-[#e2dac6] px-5 pb-6 pt-5 sm:px-6">
                <div className="space-y-5 text-sm leading-7 text-[#54606f]">
                  <p><span className="font-medium text-[#26344d]">Tên văn bản được nhắc trong tài liệu:</span> {item.mentioned_name ?? item.title}.</p>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[#5c6675]">
                    <span>Nguồn:</span>
                    <Badge variant="outline" className="rounded-md">{sourceLabel(item.source)}</Badge>
                    {item.publisher && <span>Đối chiếu tại {item.publisher}</span>}
                  </div>
                  {item.url && (
                    <p className="break-all">
                      <span className="font-medium text-[#26344d]">URL: </span>
                      <a href={item.url} target="_blank" rel="noreferrer" className="text-blue-700 underline underline-offset-4 hover:text-blue-900">{item.url}</a>
                    </p>
                  )}
                  <div>
                    <p className="font-medium text-[#26344d]">Lý do liên quan</p>
                    <p className="mt-1">{item.reason}</p>
                  </div>
                  <div>
                    <p className="font-medium text-[#26344d]">Citation trong tài liệu</p>
                    <CitationButtonList ids={item.citation_ids} report={report} onSelectCitation={onSelectCitation} />
                  </div>
                  {item.excerpt && (
                    <blockquote className="rounded-lg border-l-4 border-[#c9a86a] bg-[#f3ecdb] px-4 py-3 text-[#5c6675]">
                      {item.excerpt}
                    </blockquote>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      ) : <EmptyState title="Chưa phát hiện văn bản liên quan" description="Tài liệu không nhắc đến căn cứ cụ thể hoặc không có kết quả phù hợp từ các nguồn web được phép." />}
    </div>
  );
}
function SummarySectionContent({
  items,
  report,
  onSelectSources,
}: {
  items: ReadonlyArray<{ text: string; citation_ids: string[] }>;
  report: ReportResponse;
  onSelectSources: (citationIds: string[]) => void;
}) {
  if (!items.length) {
    return <p className="mt-5 text-sm text-[#7b8494]">Chưa có nội dung trong mục này.</p>;
  }

  const summaryItems = items
    .map((item) => ({ ...item, text: item.text.trim() }))
    .filter((item) => Boolean(item.text));
  const citationIds = Array.from(
    new Set(summaryItems.flatMap((item) => item.citation_ids)),
  ).filter((id) => Boolean(report.citations[id]));

  return (
    <div className="mt-5 border-l-2 border-[#ead9b5] pl-4">
      <ul className="space-y-3 pl-5 text-[15px] leading-7 text-[#2e3a4d] marker:text-[#996515]">
        {summaryItems.map((item, index) => (
          <li key={`${item.text}-${index}`} className="list-disc pl-1">
            {item.text}
          </li>
        ))}
      </ul>
      {citationIds.length > 0 && (
        <Button
          type="button"
          variant="outline"
          className="mt-4 border-[#996515] text-[#6f4710] hover:bg-[#f6eeda]"
          onClick={() => onSelectSources(citationIds)}
        >
          <BookOpenText className="size-4" />
          Nguồn tóm tắt
          <Badge variant="secondary" className="ml-1 rounded-full font-mono text-[10px]">
            {citationIds.length}
          </Badge>
        </Button>
      )}
    </div>
  );
}

export function CitationButtonList({ ids, report, onSelectCitation }: { ids: string[]; report: ReportResponse; onSelectCitation: (citationId: string) => void }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const validIds = Array.from(new Set(ids)).filter((id) => Boolean(report.citations[id]));
  const hasMore = validIds.length > 3;
  const visibleIds = isExpanded ? validIds : validIds.slice(0, 3);

  if (!validIds.length) return null;

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      {visibleIds.map((id) => <CitationButton key={id} citationId={id} report={report} onSelectCitation={onSelectCitation} />)}
      {hasMore && (
        <button
          type="button"
          aria-expanded={isExpanded}
          onClick={() => setIsExpanded((current) => !current)}
          className="rounded px-1 py-1 text-xs font-medium text-[#6f4710] underline decoration-[#c9a86a] underline-offset-4 transition hover:text-[#5a390c] focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          {isExpanded ? "(Thu gọn)" : "(Xem thêm)"}
        </button>
      )}
    </div>
  );
}

function CitationButton({ citationId, report, onSelectCitation }: { citationId: string; report: ReportResponse; onSelectCitation: (citationId: string) => void }) {
  const citation = report.citations[citationId];
  if (!citation) return null;
  return (
    <button type="button" onClick={() => onSelectCitation(citationId)} className="inline-flex items-center gap-1.5 rounded-full bg-[#996515] px-2.5 py-1 font-mono text-[11px] text-white transition hover:bg-[#6f4710] focus-visible:outline-2 focus-visible:outline-offset-2">
      <Quote className="size-3" /> {citationLabel(citation)}
    </button>
  );
}

function CitationDrawer({
  report,
  citationIds,
  pages,
  sourceKind,
  isLoading,
  error,
  onClose,
}: {
  report: ReportResponse;
  citationIds: string[];
  pages: Record<number, PageResponse>;
  sourceKind: "summary" | "citation";
  isLoading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  const citations = citationIds
    .map((id) => ({ id, citation: report.citations[id] }))
    .filter((item): item is { id: string; citation: CitationMeta } => Boolean(item.citation));
  const pageNumbers = Array.from(
    new Set(citations.map((item) => item.citation.page)),
  ).sort((left, right) => left - right);
  const isSummarySource = sourceKind === "summary";

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={isSummarySource ? "Nguồn tóm tắt" : "Nguồn trích dẫn"}>
      <button type="button" aria-label="Đóng nguồn" className="absolute inset-0 bg-black/35" onClick={onClose} />
      <aside className="absolute inset-y-0 right-0 flex w-full max-w-[680px] flex-col border-l border-[#d3c9b2] bg-[#faf6ec] shadow-[-4px_0_12px_rgba(0,0,0,0.04)]">
        <header className="flex items-start justify-between border-b border-[#d8cfb8] p-5">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[#5c6675]">Kiểm chứng căn cứ</p>
            <h2 className="mt-1 text-xl font-semibold">{isSummarySource ? "Nguồn tóm tắt" : "Nguồn trích dẫn"}</h2>
            <p className="mt-1 text-xs text-[#5c6675]">{citations.length} đoạn nguồn trên {pageNumbers.length} trang</p>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={onClose} aria-label="Đóng"><X className="size-5" /></Button>
        </header>
        <div className="flex-1 overflow-y-auto p-5 sm:p-6">
          {!citations.length ? <InlineError message="Citation không tồn tại trong báo cáo." /> : (
            <>
              <h3 className="break-words text-lg font-semibold">{report.file_name}</h3>
              {error && <div className="mt-4"><InlineError message={error} /></div>}

              <section className="mt-6">
                <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.14em] text-[#5c6675]">Các đoạn nguồn được dùng</p>
                <div className="space-y-4">
                  {citations.map(({ id, citation }, index) => (
                    <article key={id} className="rounded-xl border border-[#d8cfb8] bg-white p-5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Badge variant="outline" className="rounded-md font-mono">{citationLabel(citation)}</Badge>
                        <span className="font-mono text-[10px] text-[#7b8494]">Nguồn {index + 1}/{citations.length}</span>
                      </div>
                      {(citation.chapter || citation.article || citation.clause) && (
                        <dl className="mt-4 grid grid-cols-[92px_1fr] gap-x-3 gap-y-2 text-sm">
                          {citation.chapter && <><dt className="text-[#7b8494]">Chương/Mục</dt><dd>{citation.chapter}</dd></>}
                          {citation.article && <><dt className="text-[#7b8494]">Điều</dt><dd>{citation.article}</dd></>}
                          {citation.clause && <><dt className="text-[#7b8494]">Khoản</dt><dd>{citation.clause}</dd></>}
                        </dl>
                      )}
                      <p className="mt-4 whitespace-pre-line text-sm leading-7 text-[#3f4a5c]">{citation.excerpt}</p>
                      <p className="mt-3 font-mono text-[10px] text-[#7b8494]">Citation ID: {id}</p>
                    </article>
                  ))}
                </div>
              </section>

              <section className="mt-7">
                <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.14em] text-[#5c6675]">Bản xem trang gốc đã dùng</p>
                {isLoading && (
                  <p className="flex items-center gap-2 rounded-xl border border-[#d8cfb8] bg-white p-5 text-sm text-[#5c6675]"><LoaderCircle className="size-4 animate-spin" />Đang render {pageNumbers.length} trang tài liệu...</p>
                )}
                {!isLoading && (
                  <div className="space-y-5">
                    {pageNumbers.map((pageNumber) => {
                      const page = pages[pageNumber];
                      return (
                        <article key={pageNumber} className="rounded-xl border border-[#d8cfb8] bg-white p-4 sm:p-5">
                          <div className="mb-4 flex items-center justify-between gap-3">
                            <Badge variant="outline" className="rounded-md font-mono">Trang {pageNumber}</Badge>
                            <span className="text-xs text-[#7b8494]">Đối chiếu trực tiếp với bản gốc</span>
                          </div>
                          {page?.source_preview ? (
                            <div className="overflow-hidden rounded-lg border border-[#d8cfb8] bg-[#e8e0cd]">
                              <img
                                src={page.source_preview.data_url}
                                alt={`Trang ${pageNumber} của ${report.file_name}`}
                                width={page.source_preview.width}
                                height={page.source_preview.height}
                                className="h-auto w-full"
                              />
                            </div>
                          ) : (
                            <p className="rounded-lg border border-dashed border-[#d8cfb8] bg-[#faf6ec] px-4 py-5 text-sm leading-6 text-[#5c6675]">
                              Chưa có ảnh trang gốc cho trang này. PDF mới tải lên sẽ có preview; DOCX chỉ hiển thị các đoạn văn bản đã trích xuất ở phía trên.
                            </p>
                          )}
                        </article>
                      );
                    })}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

function ChatPopup({
  open,
  report,
  messages,
  question,
  canAsk,
  isAsking,
  error,
  onOpen,
  onClose,
  onQuestionChange,
  onSubmit,
  onSelectCitation,
}: {
  open: boolean;
  report: ReportResponse;
  messages: ChatMessage[];
  question: string;
  canAsk: boolean;
  isAsking: boolean;
  error: string | null;
  onOpen: () => void;
  onClose: () => void;
  onQuestionChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onSelectCitation: (citationId: string) => void;
}) {
  if (!open) {
    return (
      <>
        <button
          type="button"
          onClick={onOpen}
          aria-expanded="false"
          aria-controls="result-chat-panel"
          className="fixed bottom-4 right-4 z-40 flex items-center gap-3 rounded-full bg-[#1b2a44] px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-[#2a3a56] focus-visible:outline-2 focus-visible:outline-offset-2 md:hidden"
        >
          <MessageSquareText className="size-4" />
          Hỏi về kết quả
        </button>
        <button
          type="button"
          onClick={onOpen}
          aria-expanded="false"
          aria-controls="result-chat-panel"
          className="fixed right-0 top-1/2 z-40 hidden -translate-y-1/2 flex-col items-center gap-3 rounded-l-xl border border-r-0 border-[#2a3a56] bg-[#1b2a44] px-3 py-5 text-white shadow-[-4px_4px_18px_rgba(0,0,0,0.12)] transition hover:bg-[#2a3a56] focus-visible:outline-2 focus-visible:outline-offset-2 md:flex"
        >
          <span className="flex size-8 items-center justify-center rounded-lg bg-white/10">
            <MessageSquareText className="size-4" />
          </span>
          <span className="-rotate-180 text-xs font-semibold tracking-wide [writing-mode:vertical-rl]">
            Hỏi về kết quả
          </span>
        </button>
      </>
    );
  }

  return (
    <aside
      id="result-chat-panel"
      className="fixed inset-y-0 right-0 z-40 flex h-dvh w-full flex-col overflow-hidden border-l border-[#d3c9b2] bg-white shadow-[-8px_0_32px_rgba(0,0,0,0.10)] sm:w-[430px]"
      role="dialog"
      aria-label="Hỏi đáp về kết quả"
      aria-modal="false"
    >
      <header className="shrink-0 border-b border-[#d3c9b2]/60 bg-[#efe7d5] px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[#5c6675]">Trợ lý theo ngữ cảnh</p>
            <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold"><MessageSquareText className="size-4" />Hỏi về kết quả</h2>
            <p title={report.file_name} className="mt-1 max-w-[310px] truncate text-xs text-[#54606f]">{report.file_name}</p>
          </div>
          <Button type="button" variant="ghost" size="icon" className="shrink-0" onClick={onClose} aria-label="Ẩn cửa sổ hỏi đáp"><X className="size-4" /></Button>
        </div>
        <p className="mt-3 border-l-2 border-[#996515] bg-white px-3 py-2 text-xs leading-5 text-[#3f4a5c]">
          Phạm vi: tóm tắt, thuật ngữ, câu hỏi phản biện, văn bản liên quan và căn cứ trong kết quả này.
        </p>
      </header>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5" aria-live="polite">
        {!messages.length && (
          <div>
            <p className="text-sm font-medium">Câu hỏi gợi ý</p>
            <p className="mt-1 text-xs leading-5 text-[#5c6675]">Chọn để điền vào ô hỏi; hệ thống sẽ không tự gửi.</p>
            <div className="mt-3 space-y-2">
              {report.suggested_questions.slice(0, 2).map((item) => (
                <button key={item.question} type="button" onClick={() => onQuestionChange(item.question)} className="w-full rounded-lg border border-[#d8cfb8] bg-[#faf6ec] p-3 text-left text-xs leading-5 transition hover:border-[#7b8494] hover:bg-white">
                  {item.question}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message, index) => message.role === "user" ? (
          <div key={`user-${index}`} className="flex justify-end"><div className="max-w-[88%] rounded-xl rounded-tr-sm bg-[#e6ddca] px-4 py-3"><p className="text-sm leading-6">{message.text}</p></div></div>
        ) : (
          <div key={`assistant-${index}`} className="max-w-[94%]">
            <p className="mb-2 flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-[#5c6675]"><MessageSquareText className="size-4" />Antipaper AI</p>
            <div className={cn("rounded-xl rounded-tl-sm border px-4 py-3", message.insufficientEvidence ? "border-amber-300 bg-amber-50" : "border-[#d3c9b2] bg-white")}>
              <p className="text-sm leading-6">{message.text}</p>
              {message.insufficientEvidence ? <Badge variant="outline" className="mt-4 border-amber-400">Không đủ bằng chứng</Badge> : <CitationButtonList ids={message.citationIds} report={report} onSelectCitation={onSelectCitation} />}
              <div className="mt-4 flex items-center justify-between border-t border-[#e2dac6] pt-3 text-xs text-[#7b8494]">
                <span>{formatLatency(message.latencyMs)}</span>
                <button type="button" className="inline-flex items-center gap-1 hover:text-black" onClick={() => void navigator.clipboard?.writeText(message.text)}><Copy className="size-3.5" />Sao chép</button>
              </div>
            </div>
          </div>
        ))}
        {isAsking && <p className="flex items-center gap-2 text-sm text-[#5c6675]"><LoaderCircle className="size-4 animate-spin" />Đang tìm bằng chứng trong tài liệu...</p>}
      </div>
      <div className="shrink-0 border-t border-[#d3c9b2]/60 bg-[#faf6ec] px-4 pb-[max(12px,env(safe-area-inset-bottom))] pt-3">
        {error && <InlineError className="mb-3" message={error} />}
        <form onSubmit={onSubmit}>
          <label htmlFor="result-question" className="sr-only">Câu hỏi về kết quả</label>
          <div className="flex items-end rounded-lg border border-[#d3c9b2] bg-white p-2 shadow-sm focus-within:border-black">
            <textarea id="result-question" value={question} onChange={(event) => onQuestionChange(event.target.value)} disabled={!canAsk || isAsking} rows={2} placeholder="Đặt câu hỏi về tài liệu..." className="min-h-12 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none disabled:cursor-not-allowed" />
            <Button type="submit" disabled={!canAsk || isAsking || !question.trim()} size="icon" className="bg-[#996515] text-white" aria-label="Gửi câu hỏi"><SendHorizontal className="size-4" /></Button>
          </div>
        </form>
        <p className="mt-2 text-center text-[10px] text-[#7b8494]">Thiếu bằng chứng sẽ được từ chối thay vì suy đoán.</p>
      </div>
    </aside>
  );
}

type HistorySession = { key: string; documentId: string | null; title: string; tasks: TaskHistoryItem[]; documentTask: TaskHistoryItem | null };

function HistoryWorkspace({
  page,
  statusFilter,
  typeFilter,
  isLoading,
  error,
  onStatusFilter,
  onTypeFilter,
  onRetry,
  onOpenDocument,
  onDeleteSession,
  deletingSessionKey,
  onPrevious,
  onNext,
}: {
  page: TaskHistoryPage;
  statusFilter: DocumentStatus | "";
  typeFilter: TaskType | "";
  isLoading: boolean;
  error: string | null;
  onStatusFilter: (value: DocumentStatus | "") => void;
  onTypeFilter: (value: TaskType | "") => void;
  onRetry: () => void;
  onOpenDocument: (item: TaskHistoryItem) => void;
  onDeleteSession: (session: HistorySession) => void;
  deletingSessionKey: string | null;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const sessions = useMemo(() => groupHistory(page.items), [page.items]);
  return (
    <div>
      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <SectionHeading eyebrow=" " title="Lịch sử xử lý" description=" " />
        <div className="flex shrink-0 gap-2">
          <label className="text-xs text-[#5c6675]">Trạng thái<select value={statusFilter} onChange={(event) => onStatusFilter(event.target.value as DocumentStatus | "")} className="mt-1 block h-9 rounded-lg border border-[#cfc5ac] bg-white px-3 text-sm text-[#1b2a44]"><option value="">Tất cả</option><option value="completed">Hoàn tất</option><option value="processing">Đang xử lý</option><option value="queued">Đang chờ</option><option value="failed">Thất bại</option></select></label>
          <label className="text-xs text-[#5c6675]">Loại tác vụ<select value={typeFilter} onChange={(event) => onTypeFilter(event.target.value as TaskType | "")} className="mt-1 block h-9 rounded-lg border border-[#cfc5ac] bg-white px-3 text-sm text-[#1b2a44]"><option value="">Tất cả</option><option value="document_processing">Xử lý tài liệu</option><option value="question_answer">Hỏi đáp</option></select></label>
        </div>
      </div>
      <div className="mt-7 flex items-center justify-between rounded-xl border border-[#d8cfb8] bg-white px-5 py-4">
        <div><strong className="text-2xl">{page.total}</strong><span className="ml-2 text-sm text-[#5c6675]">tác vụ được ghi nhận</span></div>
        <Button type="button" variant="outline" onClick={onRetry} disabled={isLoading}><RefreshCcw className={cn("size-4", isLoading && "animate-spin")} />Làm mới</Button>
      </div>
      {error && <div className="mt-5"><InlineError message={error} /><Button type="button" variant="outline" className="mt-3" onClick={onRetry}>Thử lại</Button></div>}
      {isLoading ? <div className="flex min-h-[300px] items-center justify-center text-sm text-[#5c6675]"><LoaderCircle className="mr-2 size-5 animate-spin" />Đang tải lịch sử...</div> : !sessions.length && !error ? <EmptyState title="Chưa có lịch sử phù hợp" description="Thử đổi bộ lọc hoặc tải tài liệu mới để bắt đầu một phiên." /> : (
        <div className="mt-5 space-y-4">
          {sessions.map((session) => <HistorySessionCard key={session.key} session={session} onOpenDocument={onOpenDocument} onDelete={() => onDeleteSession(session)} isDeleting={deletingSessionKey === session.key} />)}
        </div>
      )}
      {page.total > page.limit && (
        <div className="mt-6 flex items-center justify-between">
          <span className="text-sm text-[#5c6675]">Hiển thị {page.offset + 1}–{Math.min(page.offset + page.items.length, page.total)} / {page.total}</span>
          <div className="flex gap-2"><Button type="button" variant="outline" size="icon" aria-label="Trang trước" disabled={page.offset === 0} onClick={onPrevious}><ChevronLeft className="size-4" /></Button><Button type="button" variant="outline" size="icon" aria-label="Trang sau" disabled={page.offset + page.limit >= page.total} onClick={onNext}><ChevronRight className="size-4" /></Button></div>
        </div>
      )}
    </div>
  );
}

function HistorySessionCard({ session, onOpenDocument, onDelete, isDeleting }: { session: HistorySession; onOpenDocument: (item: TaskHistoryItem) => void; onDelete: () => void; isDeleting: boolean }) {
  const primary = session.documentTask ?? session.tasks[0];
  return (
    <article className="overflow-hidden rounded-xl border border-[#d8cfb8] bg-white">
      <header className="flex flex-col gap-4 border-b border-[#e2dac6] bg-[#faf6ec] p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><FileText className="size-5 shrink-0 text-[#996515]" /><h2 title={session.title} className="truncate font-semibold">{session.title}</h2></div>
          <p className="mt-2 text-xs text-[#7b8494]">Phiên gần nhất: {formatDate(primary.created_at)}{session.documentId ? ` · ID ${shortId(session.documentId)}` : ""}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2"><StatusBadge status={primary.status} />{session.documentTask?.status === "completed" && <Button type="button" variant="outline" onClick={() => onOpenDocument(session.documentTask!)}><BookOpenText className="size-4" />Mở báo cáo</Button>}<Button type="button" variant="outline" className="border-red-200 text-red-700 hover:bg-red-50 hover:text-red-800" onClick={onDelete} disabled={isDeleting}><Trash2 className="size-4" />{isDeleting ? "Đang xóa" : "Xóa"}</Button></div>
      </header>
      <ol className="divide-y divide-[#e8e0cd]">
        {session.tasks.map((task) => (
          <li key={task.task_id} className="grid gap-3 p-5 sm:grid-cols-[150px_minmax(0,1fr)_110px] sm:items-start">
            <div className="text-xs text-[#7b8494]">{formatDate(task.created_at)}</div>
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-sm font-medium">{task.task_type === "document_processing" ? <FileText className="size-4" /> : <FileQuestion className="size-4" />}{task.task_type === "document_processing" ? "Phân tích tài liệu" : "Câu hỏi"}</p>
              <p className="mt-1 break-words text-sm leading-6 text-[#54606f]">{task.display_name}</p>
              {task.error && <p className="mt-2 text-xs text-red-700">{task.error.code}: {task.error.message}</p>}
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-[#7b8494]"><span>{stageLabel(task.stage)}</span>{task.duration_seconds !== null && <span>{formatDuration(task.duration_seconds)}</span>}</div>
            </div>
            <div className="sm:text-right"><StatusBadge status={task.status} /><div className="mt-2 font-mono text-[10px] text-[#9199a6]">{shortId(task.task_id)}</div></div>
          </li>
        ))}
      </ol>
    </article>
  );
}

function groupHistory(items: TaskHistoryItem[]): HistorySession[] {
  const groups = new Map<string, HistorySession>();
  for (const item of items) {
    const key = item.document_id ?? item.task_id;
    const existing = groups.get(key) ?? { key, documentId: item.document_id, title: item.document_id ? `Tài liệu ${shortId(item.document_id)}` : item.display_name, tasks: [], documentTask: null };
    existing.tasks.push(item);
    if (item.task_type === "document_processing") {
      if (!existing.documentTask || new Date(item.created_at) > new Date(existing.documentTask.created_at)) existing.documentTask = item;
      existing.title = item.display_name;
    }
    groups.set(key, existing);
  }
  return Array.from(groups.values()).sort((a, b) => new Date(b.tasks[0].created_at).getTime() - new Date(a.tasks[0].created_at).getTime());
}

function StatusBadge({ status }: { status: DocumentStatus }) {
  const labels: Record<DocumentStatus, string> = { queued: "Đang chờ", processing: "Đang xử lý", completed: "Hoàn tất", failed: "Thất bại" };
  return <Badge variant="outline" className={cn("rounded-md", status === "completed" && "border-green-600 text-green-800", status === "failed" && "border-red-500 text-red-700", status === "processing" && "border-blue-500 text-blue-700")}>{labels[status]}</Badge>;
}

function SectionHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <div className="max-w-3xl"><p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[#5c6675]">{eyebrow}</p><h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1><p className="mt-3 leading-7 text-[#5c6675]">{description}</p></div>;
}

function InlineError({ message, className }: { message: string; className?: string }) {
  return <p role="alert" className={cn("flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800", className)}><AlertTriangle className="mt-0.5 size-4 shrink-0" />{message}</p>;
}

function InlineNotice({ message, className }: { message: string; className?: string }) {
  return <p className={cn("flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900", className)}><AlertTriangle className="mt-0.5 size-4 shrink-0" />{message}</p>;
}

function EmptyState({ title, description, actionLabel, onAction }: { title: string; description: string; actionLabel?: string; onAction?: () => void }) {
  return <div className="mt-7 flex min-h-[300px] flex-col items-center justify-center rounded-xl border border-dashed border-[#cfc5ac] bg-white p-8 text-center"><span className="flex size-12 items-center justify-center rounded-full bg-[#e8e0cd]"><FileQuestion className="size-5" /></span><h2 className="mt-4 font-semibold">{title}</h2><p className="mt-2 max-w-md text-sm leading-6 text-[#5c6675]">{description}</p>{actionLabel && onAction && <Button type="button" className="mt-5" onClick={onAction}>{actionLabel}</Button>}</div>;
}

function sourceLabel(value: string) {
  if (value === "cited_in_document") return "Được dẫn trong tài liệu";
  if (value === "tavily") return "Tavily (nguồn đã lọc)";
  return value;
}

function shortId(value: string) {
  return value.length > 14 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Bangkok" }).format(new Date(value));
}

function formatDuration(value: number) {
  return value < 1 ? `${Math.round(value * 1000)} ms` : `${value.toFixed(1)} giây`;
}

function formatLatency(value: number) {
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} giây`;
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function persistActiveDocument(documentId: string | null) {
  try {
    if (documentId) window.localStorage.setItem(ACTIVE_DOCUMENT_STORAGE_KEY, documentId);
    else window.localStorage.removeItem(ACTIVE_DOCUMENT_STORAGE_KEY);
  } catch {
    // Storage is optional; the active in-memory session remains functional.
  }
}

function readActiveDocument(): string | null {
  try {
    return window.localStorage.getItem(ACTIVE_DOCUMENT_STORAGE_KEY);
  } catch {
    return null;
  }
}
