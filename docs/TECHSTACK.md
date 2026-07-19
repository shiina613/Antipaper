# Technical Stack — Antipaper

## 1. Context

Tài liệu này mô tả **những thành phần đang được mã nguồn sử dụng**, không phải kiến trúc
pilot dự kiến. Phiên bản Python lấy từ `pyproject.toml`; phiên bản frontend lấy từ
`frontend/package.json` và `frontend/package-lock.json`. Các đề xuất như PostgreSQL,
Redis, vector database, OCR, OpenTelemetry, OIDC/SAML, object storage và generated
OpenAPI client **chưa có trong repository**.

## 2. Runtime Architecture

```text
Browser
  └─ React 19 SPA (Vite development server :5173)
       └─ /api/v1/* proxy trong development
            └─ FastAPI/Uvicorn (:8000)
                 ├─ ThreadPoolExecutor (3 workers, cùng process)
                 ├─ PyMuPDF / python-docx → normalized document
                 ├─ in-memory lexical index → grounded Q&A
                 ├─ OpenAI-compatible LLM map–reduce report generation
                 ├─ Tavily HTTP enrichment tùy chọn
                 └─ SQLite → task history
```

Ứng dụng là MVP đơn tiến trình. Tài liệu upload, báo cáo, index, trang đã trích xuất và
future xử lý chỉ tồn tại trong RAM; SQLite chỉ lưu lịch sử task. Khởi động lại backend sẽ
không thể mở lại report cũ, dù item lịch sử vẫn còn.

## 3. Current Technical Stack

### 3.1 Backend

| Layer | Công nghệ đang dùng | Cách dùng trong mã nguồn | Giới hạn hiện tại |
|---|---|---|---|
| Runtime | Python `>=3.11` | Runtime backend; cấu hình packaging bằng setuptools | Không có lock file Python. |
| API | FastAPI `>=0.100`, Uvicorn `[standard] >=0.23` | REST API `/api/v1`, upload multipart, OpenAPI tại `/docs`, lifespan shutdown | Một process; không có reverse proxy/production deployment config trong repo. |
| Schema | Pydantic `>=2.0` | Request/response, report, citation và task-history contracts | Client TypeScript được viết thủ công, không sinh từ OpenAPI. |
| HTTP/LLM | httpx `>=0.25` | Gọi trực tiếp endpoint Chat Completions tương thích OpenAI, JSON response format, timeout 10 giây, không retry | Không dùng SDK `openai`, gateway, streaming hay background retry. Không có key hoặc output không đạt quality gate thì report fail-closed. |
| Xử lý nền | `concurrent.futures.ThreadPoolExecutor(max_workers=3)` và `asyncio` chuẩn thư viện | Chạy pipeline document và enrichment trong process | Không durable, không queue/DLQ/backpressure, không scale-out; worker bị mất khi process dừng. |
| PDF | PyMuPDF / `fitz` `>=1.23` | Đọc native text theo trang, nhận diện bảng native, render preview PNG base64 | Không OCR; PDF scan không có native text không được phục hồi. |
| DOCX | python-docx `>=1.1` | Đọc paragraph và table từ bytes; chuẩn hóa thành một logical page | DOCX không có phân trang nguồn đáng tin cậy; không có image preview. |
| Retrieval | Inverted index lexical tự cài đặt | Token matching, top-k evidence, citation validation và grounded extractive Q&A | Không có BM25 package, embeddings, reranker hay vector store. |
| Intelligence | LLM map–reduce + heuristic cục bộ | Map toàn bộ chunk có citation, reduce bốn phần summary và sinh năm câu hỏi phản biện; thuật ngữ giữ heuristic | LLM là critical path; giới hạn batch/concurrency phải phù hợp deadline 48 giây. |
| Enrichment | Regex extractor + Tavily Search REST qua httpx | Tìm văn bản liên quan ngoài critical path, có domain allowlist | Chỉ chạy khi có `TAVILY_API_KEY`; có thể gửi query có title/số hiệu ra dịch vụ ngoài. Không dùng Tavily SDK. |
| Persistence | `sqlite3` chuẩn thư viện | `.runtime/history.sqlite3` lưu trạng thái, lỗi và thời lượng task | Không lưu binary file, report, citation index hay user/session thực; không phù hợp multi-instance. |
| Cấu hình | python-dotenv `>=1.0` | Nạp `.env` ở API/CLI | `.env` chỉ phù hợp local; chưa tích hợp secret manager. |
| Logging | `logging` chuẩn thư viện | Log HTTP với method, path, status, duration, content length | Không có metrics, trace exporter hay OpenTelemetry. |

### 3.2 Frontend

| Layer | Công nghệ đang dùng | Cách dùng trong mã nguồn | Ghi chú |
|---|---|---|---|
| Runtime/build | Node.js `20+`, Vite `^7.0.0` | Dev server, production build và proxy `/api/v1` đến `ANTIPAPER_BACKEND_URL` | Port development mặc định của Vite là `5173`; production cần reverse proxy để giữ same-origin. |
| Framework | React `19.2.0`, React DOM `19.2.0`, TypeScript `^5` | SPA client-side, `createRoot`, `StrictMode` | |
| Routing | `react-router-dom` `^7.9.0` | `BrowserRouter`: `/` cho landing, `/app` cho workspace | Routing hoàn toàn ở client. |
| Styling | Tailwind CSS `^4`, `@tailwindcss/vite`, `tw-animate-css` | CSS-first Tailwind 4 trong `globals.css`, custom token/animation | Không có Tailwind config file; plugin chạy qua Vite. |
| UI primitives | `@base-ui/react` `^1.6.0` | Accordion primitive; component layout theo cấu trúc shadcn-style | `components.json` là cấu hình shadcn UI, nhưng không có dependency `shadcn/ui`; button/badge/accordion là component nội bộ. |
| UI utilities | `class-variance-authority`, `clsx`, `tailwind-merge` | Variants cho button/badge và hàm `cn()` | Không có component library khác đang được import. |
| Icon | `lucide-react` `^0.553.0` | Icons toàn bộ landing/workspace | — |
| Browser API | `fetch`, `FormData`, `Headers`, `URLSearchParams`, `crypto.randomUUID`, `localStorage` | API client thủ công, upload, tạo/lưu UUID người dùng và document ID đang mở | `localStorage` giữ identifier, không giữ file/report. |
| Fonts/assets | Google Fonts qua `index.html`; PNG/ICO trong `public/` | Be Vietnam Pro, Space Mono, Spectral; motifs và favicon | Fonts phụ thuộc mạng khi không được browser cache. |
| Lint/type/build | ESLint 9, `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`, TypeScript compiler, `@vitejs/plugin-react` | `npm run lint`, `npm run build` | Package lock là nguồn tái lập dependency Node. |

### 3.3 Testing and Evaluation

| Scope | Công nghệ | Trạng thái sử dụng |
|---|---|---|
| Backend unit/lifecycle | pytest `>=8` | `tests/test_lifecycle.py`; test path được khai báo trong `pyproject.toml`. |
| Lint Python | Ruff `>=0.8` | Cấu hình Python 3.11, line length 100. |
| Frontend quality | ESLint và `tsc --noEmit` | Chạy qua `npm run lint` và `npm run build`. |
| Benchmark cold start | Standard-library `subprocess`/`time` | `scripts/benchmark_cold.py`; không có framework benchmark ngoài. |
| Release evaluation | DeepEval `4.1.0` | Có test/dataset trong `evals/`; cần LLM credentials. Dependency này có trong môi trường phát triển và `requirement.txt`, nhưng hiện chưa khai báo trong `pyproject.toml`. |

## 4. Data Flow and Operational Constraints

1. Frontend kiểm tra extension/MIME và kích thước 25 MB, sau đó `POST` multipart vào FastAPI.
2. Backend tạo task history SQLite, giữ bytes trong RAM và gửi job vào thread pool ba worker.
3. `DocumentIngestor` trích xuất PDF/DOCX, chuẩn hóa chunk/citation; retrieval index cũng chỉ giữ trong RAM.
4. `DocumentOrchestrator` map toàn bộ chunk theo batch, reduce thành report có citation và sinh câu hỏi phản biện. Thiếu cấu hình, timeout, JSON/schema lỗi hoặc citation không hợp lệ làm task thất bại; không có heuristic fallback cho summary/câu hỏi.
5. Q&A dùng lexical retrieval và citation validation. Tavily enrichment là task nền tùy chọn sau report.
6. Frontend poll status, tải report/page preview và gọi Q&A bằng `fetch` relative URL.

## 5. Configuration and Security Posture

| Biến | Vai trò thực tế |
|---|---|
| `LLM_API_KEY` | Bắt buộc để tạo report; vắng key làm task thất bại với `LLM_NOT_CONFIGURED`. |
| `LLM_BASE_URL`, `LLM_API_URL`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_OUTPUT_TOKENS` | Endpoint/model/timeout/ngân sách output OpenAI-compatible. |
| `LLM_MAP_BATCH_CHARS`, `LLM_MAP_MAX_BATCH_CHARS`, `LLM_MAP_TARGET_BATCHES`, `LLM_MAP_CONCURRENCY` | Batch thích ứng theo toàn bộ text, tối đa ba map request đồng thời cho mỗi tài liệu. |
| `MAX_LLM_CONCURRENCY` | Giới hạn request LLM đang hoạt động trên toàn tiến trình, tránh ba worker tạo burst không kiểm soát. |
| `MAX_ANALYZABLE_TEXT_CHARS` | Trần text đã trích xuất cho SLA; vượt trần trả `ANALYSIS_TEXT_LIMIT_EXCEEDED` trước khi gọi LLM. |
| `PROCESSING_DEADLINE_SECONDS` | Deadline thực của worker, mặc định 110 giây; map/reduce/questions bị hủy theo ngân sách pha. |
| `HISTORY_DB_PATH` | Đường dẫn SQLite history, mặc định `.runtime/history.sqlite3`. |
| `TAVILY_API_KEY`, `TAVILY_BASE_URL`, `TAVILY_ALLOWED_DOMAINS`, `TAVILY_TIMEOUT_SECONDS`, `TAVILY_MAX_RESULTS` | Cấu hình enrichment Tavily tùy chọn. |
| `ANTIPAPER_BACKEND_URL` | Target Vite proxy khi development. |
| `FRONTEND_ORIGIN` | Có trong `.env.example` nhưng **chưa được backend đọc**. |

MVP chấp nhận `X-User-ID` do client gửi; frontend tạo UUID và lưu ở `localStorage`. FastAPI hiện cấu hình CORS `allow_origins=["*"]` cùng `allow_credentials=True`. Đây không phải authentication/authorization production; không có OIDC/SAML, RBAC, tenant isolation, rate limit hoặc secret manager.

## 6. Dependency Manifests

- `pyproject.toml` là metadata package và phạm vi runtime/dev Python hiện hữu.
- `requirement.txt` là manifest cài đặt pip tương đương, bổ sung DeepEval cho release suite. Cài backend/quality/evaluation bằng `python -m pip install -r requirement.txt`.
- `frontend/package.json` khai báo dependency Node và `frontend/package-lock.json` khóa dependency tree. Cài frontend bằng `npm.cmd ci` trong `frontend/`.

## 7. Strategic Recommendations

1. Tách document state khỏi memory và thay thread pool bằng queue/worker durable trước khi chạy nhiều instance hoặc cần khôi phục tác vụ.
2. Thay CORS wildcard và header identity bằng reverse proxy TLS, OIDC/OAuth2 và authorization gắn tenant trước khi xử lý tài liệu nội bộ.
3. Lưu object/report/index theo policy bảo mật; chỉ khi đó mới có thể cho phép mở lại lịch sử một cách nhất quán.
4. Đánh giá OCR, embeddings/hybrid retrieval, PostgreSQL/pgvector và observability bằng workload đại diện trước khi đưa vào critical path.
5. Khai báo DeepEval trong `pyproject.toml` optional dependency nếu release suite là gate bắt buộc; hiện `requirement.txt` đã bảo đảm môi trường chạy suite đó.
