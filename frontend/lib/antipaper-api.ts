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
