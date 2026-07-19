# Antipaper

Antipaper là ứng dụng **FastAPI (backend) + React/Vite (frontend)** cho việc trích xuất PDF/DOCX
gốc (không OCR), sinh báo cáo có dẫn chứng, hỏi–đáp trích dẫn theo từ khóa, và tùy chọn làm giàu
tài liệu liên quan chạy nền.

- Backend: `src/` — API tại `http://127.0.0.1:8000`
- Frontend: `frontend/` — dashboard tại `http://localhost:5173`

## Kiến trúc & cách các thành phần nối với nhau

```
Trình duyệt ──► Vite (:5173, development) ──proxy /api/v1/*──► FastAPI (:8000) ──► Xử lý trong tiến trình
```

- Frontend gọi đường dẫn tương đối `/api/v1/...` ([frontend/src/lib/antipaper-api.ts](frontend/src/lib/antipaper-api.ts)).
- Vite development server **proxy** các request đó sang backend qua
  [frontend/vite.config.ts](frontend/vite.config.ts). Đích proxy lấy từ biến môi trường
  `ANTIPAPER_BACKEND_URL` (mặc định `http://127.0.0.1:8000`).
- Nhờ proxy này, trình duyệt gọi cùng origin nên không phụ thuộc CORS khi chạy local.

## Yêu cầu môi trường

- **Python 3.11+** (khuyến nghị 3.12)
- **Node.js 20+** (frontend dùng Vite 7 / React 19)

## Chạy backend

Chạy từ **thư mục gốc của repo** (lệnh `python -m src` cần thư mục gốc để import package `src`):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m src --reload
```

Tham số hỗ trợ: `--host` (mặc định `127.0.0.1`), `--port` (mặc định `8000`), `--reload`,
`--log-level`. Uvicorn nạp app `src.main:app`.

Kiểm tra nhanh backend đã sống:

```powershell
curl http://127.0.0.1:8000/health
# {"status":"ok","service":"antipaper-backend","version":"0.1.0","llm_status":"..."}
```

Tài liệu API tương tác: `http://127.0.0.1:8000/docs`.

## Chạy frontend

Ở terminal thứ hai:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

Nếu backend chạy ở host/port khác, đặt trước khi `npm run dev`:

```powershell
$env:ANTIPAPER_BACKEND_URL = "http://127.0.0.1:8000"
```

## Biến môi trường (`.env`)

Sao chép từ [.env.example](.env.example). Không commit bí mật.

| Biến | Vai trò |
|---|---|
| `OPENAI_API_KEY` / `LLM_API_KEY` | Khóa LLM bắt buộc để phát hành báo cáo. Thiếu khóa làm document task thất bại (`llm_status: disabled`). |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_OUTPUT_TOKENS` | Cấu hình endpoint/model/giới hạn một lượt gọi LLM. |
| `LLM_MAP_BATCH_CHARS`, `LLM_MAP_MAX_BATCH_CHARS`, `LLM_MAP_TARGET_BATCHES`, `LLM_MAP_CONCURRENCY` | Batch thích ứng và số map request đồng thời của pipeline tổng hợp phân tầng. |
| `MAX_LLM_CONCURRENCY` | Request LLM tối đa đang hoạt động trên toàn tiến trình. |
| `MAX_ANALYZABLE_TEXT_CHARS` | Trần text trích xuất được xử lý trong SLA (mặc định 600.000 ký tự). |
| `PROCESSING_DEADLINE_SECONDS` | Hạn xử lý thực mỗi tài liệu (mặc định 110s). |
| `HISTORY_DB_PATH` | SQLite lưu lịch sử tác vụ (mặc định `.runtime/history.sqlite3`). |
| `TAVILY_*`, `RELATED_DOCUMENT_MAX_REFERENCES` | Làm giàu tài liệu liên quan chạy nền (tùy chọn). |
| `FRONTEND_ORIGIN` | Origin frontend cho cấu hình CORS. |

## Mô hình runtime

- Mỗi lần upload nhận một UUID mới và được xử lý từ bytes; file trùng nhau **không** dùng lại kết quả.
- Tài liệu, payload báo cáo, preview trang và chỉ mục từ khóa chỉ tồn tại trong bộ nhớ tiến trình.
- SQLite tại `.runtime/history.sqlite3` **chỉ** lưu lịch sử tác vụ. Sau khi khởi động lại, lịch sử
  vẫn hiển thị nhưng muốn xem lại báo cáo cũ thì phải upload lại.
- File scan/chỉ-có-OCR nằm ngoài phạm vi hỗ trợ (cố ý).

## API v1 (được frontend proxy dưới `/api/v1`)

| Method & path | Chức năng |
|---|---|
| `GET /health`, `GET /api/v1/health` | Kiểm tra sức khỏe + trạng thái LLM |
| `POST /api/v1/documents` | Upload tài liệu (trả `202`, kèm `document_id`) |
| `GET /api/v1/documents/{id}/status` | Trạng thái xử lý |
| `GET /api/v1/documents/{id}/report` | Báo cáo có dẫn chứng |
| `POST /api/v1/documents/{id}/questions` | Hỏi–đáp trích dẫn |
| `GET /api/v1/documents/{id}/pages/{n}` | Preview một trang |
| `GET /api/v1/history`, `GET /api/v1/history/{task_id}` | Lịch sử tác vụ |

## Kiểm thử & chất lượng

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
Set-Location frontend; npm.cmd run lint; npm.cmd run build
.\.venv\Scripts\python.exe scripts\benchmark_cold.py data\03.pdf
```

> **Lưu ý Windows:** nếu `pytest` báo `PermissionError [WinError 5]` khi tạo thư mục tạm, chỉ định
> nơi ghi được: `python -m pytest -q --basetemp .runtime\pytest`.

## Cấu trúc thư mục

```
src/            # Backend FastAPI (chạy bằng `python -m src`)
  main.py         # Khai báo app + route
  cli.py          # Entrypoint uvicorn (src.main:app)
  services/       # orchestrator, documents
  ingestion/      # Trích xuất PDF/DOCX
  intelligence/   # Contracts + map-reduce LLM; thuật ngữ heuristic cục bộ
  retrieval/      # Chỉ mục từ khóa, Q&A, citation
  persistence/    # Lịch sử SQLite
  integrations/   # LLM, Tavily
frontend/       # Dashboard React/Vite
scripts/        # benchmark_cold.py
evals/          # Bộ đo benchmark (xem ghi chú bên dưới)
data/           # PDF mẫu
docs/           # Đặc tả sản phẩm/kiến trúc (PRD.md, README.md)
```

## Ghi chú kỹ thuật

- Package backend là `src` (import tuyệt đối `src.` và import tương đối trong package). Phải chạy
  các lệnh Python từ thư mục gốc repo.
- `evals/run.py` hiện **còn hỏng** độc lập với việc đóng gói: nó import `evaluate_golden_set` và
  `load_golden_cases` từ `src.retrieval`, nhưng module golden đã bị gỡ nên hai hàm này không còn
  tồn tại. Cần khôi phục/viết lại golden set trước khi dùng lại runner này.

Xem thêm `docs/PRD.md` và `docs/README.md` cho phạm vi sản phẩm, hợp đồng API và tiêu chí phát hành.
