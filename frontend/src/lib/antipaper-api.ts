const API_BASE = "/api/v1";
const USER_ID_STORAGE_KEY = "antipaper.user-id";
const MAX_FILE_SIZE = 25 * 1024 * 1024;
const SUPPORTED_TYPES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);

export type DocumentStatus = "queued" | "processing" | "completed" | "failed";
export type ProcessingStage =
  | "queued"
  | "parsing"
  | "mapping"
  | "reducing"
  | "generating_questions"
  | "generating"
  | "ready"
  | "answering"
  | "extracting"
  | "detecting_tables"
  | "stitching"
  | "summarizing"
  | "completed"
  | "failed";
export type ApiErrorPayload = {
  error: {
    code: string;
    message: string;
    retryable: boolean;
  };
};

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export type UploadResponse = {
  document_id: string;
  status: DocumentStatus;
  task_id?: string;
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

export type ReportQuality = {
  pipeline: string;
  map_batch_count: number;
  map_wave_count?: number;
  question_count: number;
  summary_sections_complete: boolean;
  citations_valid: boolean;
  report_status: "complete" | "partial";
  passed: boolean;
  input_characters?: number;
  llm_call_count?: number;
  retry_count?: number;
  queue_ms?: number;
  stage_timings?: Array<{ stage: string; duration_ms: number }>;
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
    mentioned_name?: string | null;
    source: string;
    reason: string;
    citation_ids: string[];
    url?: string | null;
    publisher?: string | null;
    excerpt?: string | null;
  }>;
  citations: Record<string, CitationMeta>;
  generation_mode?: "llm" | "terminology_partial";
  quality?: ReportQuality | null;
  enrichment_status: "not_configured" | "pending" | "completed" | "failed";
};

export type QuestionResponse = {
  answer: string;
  insufficient_evidence: boolean;
  citation_ids: string[];
  latency_ms: number;
  task_id?: string;
};

export type TaskType = "document_processing" | "question_answer";

export type TaskHistoryItem = {
  task_id: string;
  task_type: TaskType;
  document_id: string | null;
  display_name: string;
  status: DocumentStatus;
  stage: string;
  progress: number;
  created_at: string;
  started_at: string | null;
  updated_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  error: { code: string; message: string } | null;
};

export type TaskHistoryPage = {
  items: TaskHistoryItem[];
  total: number;
  limit: number;
  offset: number;
};

export type HistoryFilters = {
  limit?: number;
  offset?: number;
  status?: DocumentStatus | "";
  taskType?: TaskType | "";
};

export type PageResponse = {
  document_id: string;
  page_number: number;
  text: string;
  blocks?: Array<{
    kind: string;
    text: string;
    page_number: number;
  }>;
  source_preview?: {
    kind: "page_image";
    mime_type: string;
    data_url: string;
    width: number;
    height: number;
    page_number: number;
  } | null;
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
    parsing: "Đọc và chuẩn hóa tài liệu",
    mapping: "Trích xuất bằng chứng toàn tài liệu",
    reducing: "Tổng hợp báo cáo có dẫn nguồn",
    generating_questions: "Sinh câu hỏi phản biện",
    generating: "Tạo báo cáo có dẫn nguồn",
    extracting: "Trích xuất văn bản",
    detecting_tables: "Nhận diện bảng",
    stitching: "Ghép nội dung",
    summarizing: "Tạo tóm tắt",
    answering: "Đang tìm bằng chứng",
    ready: "Sẵn sàng",
    completed: "Hoàn tất",
    failed: "Thất bại",
  };
  return labels[stage] ?? "Đang xử lý";
}

async function fetchApi(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  headers.set("X-User-ID", getOrCreateUserId());
  const response = await fetch(input, { ...init, headers });

  if (!response.ok) {
    let message = "Không thể kết nối backend.";
    let code: string | undefined;
    try {
      const payload = (await response.json()) as ApiErrorPayload;
      message = payload.error?.message ?? message;
      code = payload.error?.code;
    } catch {
      message = response.statusText || message;
    }
    throw new ApiRequestError(message, response.status, code);
  }

  return response;
}

async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetchApi(input, init);
  return (await response.json()) as T;
}

function getOrCreateUserId(): string {
  if (typeof window === "undefined") return "demo-user";
  try {
    const existing = window.localStorage.getItem(USER_ID_STORAGE_KEY);
    if (existing) return existing;
    const generated = `web-${window.crypto.randomUUID()}`;
    window.localStorage.setItem(USER_ID_STORAGE_KEY, generated);
    return generated;
  } catch {
    return "demo-user";
  }
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return fetchJson<UploadResponse>(`${API_BASE}/documents`, {
    method: "POST",
    body: formData,
  });
}

export function getDocumentStatus(documentId: string): Promise<StatusResponse> {
  return fetchJson<StatusResponse>(`${API_BASE}/documents/${documentId}/status`);
}

export function getDocumentReport(documentId: string): Promise<ReportResponse> {
  return fetchJson<ReportResponse>(`${API_BASE}/documents/${documentId}/report`);
}

export function askDocumentQuestion(
  documentId: string,
  question: string,
): Promise<QuestionResponse> {
  return fetchJson<QuestionResponse>(`${API_BASE}/documents/${documentId}/questions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export function getDocumentPage(documentId: string, pageNumber: number): Promise<PageResponse> {
  return fetchJson<PageResponse>(`${API_BASE}/documents/${documentId}/pages/${pageNumber}`);
}

export function getTaskHistory(filters: HistoryFilters = {}): Promise<TaskHistoryPage> {
  const params = new URLSearchParams({
    limit: String(filters.limit ?? 20),
    offset: String(filters.offset ?? 0),
  });
  if (filters.status) params.set("status", filters.status);
  if (filters.taskType) params.set("task_type", filters.taskType);

  return fetchJson<TaskHistoryPage>(`${API_BASE}/history?${params.toString()}`);
}

export async function deleteTaskHistory(taskId: string): Promise<void> {
  await fetchApi(`${API_BASE}/history/${taskId}`, { method: "DELETE" });
}

export async function deleteHistorySession(documentId: string): Promise<void> {
  await fetchApi(`${API_BASE}/history/sessions/${documentId}`, { method: "DELETE" });
}
