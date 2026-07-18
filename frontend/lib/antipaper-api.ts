const API_BASE = "/api/v1";
const ENABLE_MOCK_FALLBACK = process.env.NEXT_PUBLIC_ENABLE_MOCK_FALLBACK === "true";
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
  | "generating"
  | "ready"
  | "answering"
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
  generation_mode?: "llm" | "heuristic_fallback";
  quality?: Record<string, unknown> | null;
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
  cached: boolean;
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
};

export const mockDocumentId = "mock-antipaper-q3";

export const mockReport: ReportResponse = {
  document_id: mockDocumentId,
  file_name: "Báo cáo Tài chính Q3_2023.pdf",
  page_count: 142,
  processing_seconds: 38.2,
  generation_mode: "heuristic_fallback",
  quality: null,
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
      explanation:
        "Doanh thu sau khi trừ các khoản giảm trừ, dùng để đánh giá hiệu quả kinh doanh thực tế.",
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
    {
      term: "Trung tâm dữ liệu",
      explanation: "Hạ tầng vật lý vận hành máy chủ, lưu trữ và kết nối phục vụ các dịch vụ điện toán đám mây.",
      citation_ids: ["P14-D2"],
    },
    {
      term: "Khách hàng doanh nghiệp lớn",
      explanation: "Nhóm khách hàng tổ chức có quy mô sử dụng cao, được xác định là động lực tăng trưởng chính trong kỳ.",
      citation_ids: ["P14-D2"],
    },
    {
      term: "Tăng trưởng cùng kỳ",
      explanation: "Mức thay đổi được so sánh với cùng giai đoạn của năm trước để loại trừ ảnh hưởng mùa vụ.",
      citation_ids: ["P14-D2"],
    },
    {
      term: "Chi phí vận hành",
      explanation: "Chi phí duy trì hạ tầng và hoạt động cung cấp dịch vụ, tăng 5% trong kỳ báo cáo.",
      citation_ids: ["P18-D4"],
    },
    {
      term: "Hạ tầng số",
      explanation: "Tập hợp năng lực máy chủ, lưu trữ, mạng và nền tảng phục vụ triển khai dịch vụ số.",
      citation_ids: ["P14-D2"],
    },
    {
      term: "Lạm phát chi phí",
      explanation: "Áp lực tăng giá đầu vào được tài liệu nêu là một nguyên nhân làm chi phí vận hành tăng nhẹ.",
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
    {
      question: "Biên lợi nhuận 42% có còn bền vững nếu chi phí vận hành tiếp tục tăng?",
      rationale: "Kiểm tra sức chịu đựng tài chính trước khi phê duyệt mở rộng hạ tầng.",
      citation_ids: ["P18-D4"],
    },
    {
      question: "Hai trung tâm dữ liệu mới đã sử dụng bao nhiêu phần trăm công suất thiết kế?",
      rationale: "Làm rõ hiệu quả khai thác tài sản trước khi quyết định đầu tư bổ sung.",
      citation_ids: ["P14-D2"],
    },
    {
      question: "Tiêu chí nào được dùng để ưu tiên đầu tư IaaS hay PaaS tại khu vực phía Nam?",
      rationale: "Buộc phương án đầu tư gắn với nhu cầu thực tế và mục tiêu tăng trưởng.",
      citation_ids: ["P14-D2"],
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
      excerpt:
        "Chi phí vận hành tăng nhẹ 5% do lạm phát, tuy nhiên biên lợi nhuận gộp vẫn duy trì ở mức ổn định 42%.",
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
    parsing: "Đọc và chuẩn hóa tài liệu",
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

async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<ApiResult<T>> {
  const headers = new Headers(init?.headers);
  headers.set("X-User-ID", getOrCreateUserId());
  const response = await fetch(input, { ...init, headers });

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
  } catch (error) {
    if (!ENABLE_MOCK_FALLBACK) throw error;
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
  } catch (error) {
    if (!ENABLE_MOCK_FALLBACK) throw error;
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
  } catch (error) {
    if (!ENABLE_MOCK_FALLBACK) throw error;
    return withMock(mockReport);
  }
}

export async function askDocumentQuestion(
  documentId: string,
  question: string,
): Promise<ApiResult<QuestionResponse>> {
  try {
    return await fetchJson<QuestionResponse>(`${API_BASE}/documents/${documentId}/questions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch (error) {
    if (!ENABLE_MOCK_FALLBACK) throw error;
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
  } catch (error) {
    if (!ENABLE_MOCK_FALLBACK) throw error;
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
              kind: "text",
              text: citation[1].excerpt,
              page_number: pageNumber,
            },
          ]
        : [],
    });
  }
}

export async function getTaskHistory(filters: HistoryFilters = {}): Promise<ApiResult<TaskHistoryPage>> {
  const params = new URLSearchParams({
    limit: String(filters.limit ?? 20),
    offset: String(filters.offset ?? 0),
  });
  if (filters.status) params.set("status", filters.status);
  if (filters.taskType) params.set("task_type", filters.taskType);

  return fetchJson<TaskHistoryPage>(`${API_BASE}/history?${params.toString()}`);
}
