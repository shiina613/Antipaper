# Antipaper

Trợ lý AI giúp cán bộ đọc nhanh tài liệu họp dài, chuẩn bị câu hỏi và tra cứu bằng tiếng Việt với citation đến trang/mục/điều.
<img width="1939" height="4097" alt="mermaid-diagram-2026-07-18-075329" src="https://github.com/user-attachments/assets/e50b2b98-9fe2-4cdd-8f85-1cd4eb7334f4" />

## Trạng thái hiện tại

Kho mã nguồn đang ở mức khung kỹ thuật:

- Đã có luồng PDF bằng PyMuPDF, Streamlit MVP và giao diện Next.js tĩnh.
- Đã có FastAPI job/cache, canonical document contract, grounded Q&A và citation cấp trang/mục/điều.
- Report dùng LLM map-reduce khi cấu hình model; heuristic chỉ là fallback có gắn nhãn và không được qua release gate.
- Đã có benchmark deterministic và DeepEval; semantic embedding và DOCX production vẫn là hạng mục tiếp theo.
- Kho `data/` đã có nhiều PDF từ 40 trang; tài liệu demo được chọn qua `DEMO_DOCUMENT_PATH`, không phụ thuộc tên file.

Xem trạng thái chi tiết tại [docs/PROJECT_PROGRESS.md](docs/PROJECT_PROGRESS.md).

## Tài liệu làm việc

| Tài liệu | Mục đích |
|---|---|
| [problem.txt](problem.txt) | Đề bài và phạm vi sản phẩm |
| [docs/PRODUCT_REQUIREMENTS.md](docs/PRODUCT_REQUIREMENTS.md) | Người dùng, yêu cầu và phạm vi MVP |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Kiến trúc xử lý và quyết định kỹ thuật |
| [docs/TECH_STACK.md](docs/TECH_STACK.md) | Ngăn xếp công nghệ dùng trong 48 giờ |
| [docs/API_CONTRACT.md](docs/API_CONTRACT.md) | Hợp đồng tích hợp backend–frontend |
| [docs/BUILD_PLAN_48H.md](docs/BUILD_PLAN_48H.md) | Timeline, mốc khóa và phương án dự phòng |
| [docs/ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md) | Cách kiểm chứng tiêu chí nộp bài |
| [docs/AI_COLLABORATION_LOG.md](docs/AI_COLLABORATION_LOG.md) | Nhật ký và bằng chứng cộng tác với các công cụ AI |
| [docs/ONE_PAGE_DECK.md](docs/ONE_PAGE_DECK.md) | Nội dung deck một trang |
| `docs/TASKS_*.md` | Việc cụ thể của từng thành viên |

## Phân công 5 người

| Thành viên | Mảng phụ trách | Chi tiết |
|---|---|---|
| Hậu | Tóm tắt, thuật ngữ, câu hỏi AI và OCR fallback | [TASKS_HAU.md](docs/TASKS_HAU.md) |
| Tuấn | Nhập PDF/DOCX, parse cấu trúc, citation và LLM client | [TASKS_TUAN.md](docs/TASKS_TUAN.md) |
| Tùng | Giao diện, tích hợp, benchmark nghiệm thu, demo và deck | [TASKS_TUNG.md](docs/TASKS_TUNG.md) |
| Tùng Anh | Truy hồi, Q&A, văn bản liên quan, kiểm tra citation | [TASKS_TUNG_ANH.md](docs/TASKS_TUNG_ANH.md) |
| Hưng | FastAPI, job/cache, xử lý bottleneck runtime và đóng gói backend | [TASKS_HUNG.md](docs/TASKS_HUNG.md) |

## Cấu trúc chính

```text
Antipaper/
├── backend/              # FastAPI, orchestration, artifact cache
├── data/                 # PDF mẫu công khai
├── docs/                 # Kiến trúc, kế hoạch, kiểm thử và task
├── evals/                # Release dataset, adapters và DeepEval suite
├── evidence/             # Kết quả benchmark có truy vết
├── frontend/             # Next.js dashboard
├── scripts/              # Script demo/benchmark
├── src/intelligence/     # Tóm tắt, thuật ngữ, câu hỏi, Q&A
├── src/pipeline/         # Trích xuất và chuẩn hóa tài liệu
└── app.py                # Streamlit MVP dự phòng
```

## Chạy baseline hiện tại

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-cuda.txt
python download_yolo_table_weights.py
streamlit run app.py
```

Máy Windows có GPU NVIDIA phải dùng `requirements-cuda.txt`; `requirements.txt`
không pin CUDA và có thể khiến dependency của Ultralytics cài PyTorch CPU-only.
Luôn gọi pip qua `python -m pip` sau khi kích hoạt `.venv` để tránh vô tình cài
vào Python hệ thống (đặc biệt không dùng Python 3.14 cho môi trường demo).
Nếu `.venv` được uv tạo và không có module `pip`, dùng lệnh tương đương:

```powershell
uv pip install --python .\.venv\Scripts\python.exe -r requirements-cuda.txt
```

Kiểm tra runtime sau khi cài:

```powershell
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Baseline cần YOLO weights. Kiến trúc hackathon mới sẽ đưa YOLO ra khỏi luồng bắt buộc để ưu tiên tốc độ và độ ổn định.

Frontend tĩnh:

```powershell
cd frontend
npm install
npm run dev
```

## Chạy backend

```powershell
py -m backend --host 127.0.0.1 --port 8000 --reload
```

Hoặc dùng script Windows:

```powershell
.\scripts\run_backend.ps1
```

## Gói deploy backend

```powershell
.\scripts\package_backend.ps1
```

Bundle đầu ra mặc định nằm ở `.artifacts\antipaper-backend.zip`.

## Chạy evaluation benchmark

PR gate không gọi LLM judge và có thể chạy offline:

```powershell
python -m pytest
python -m evals.run --suite smoke --output evidence/benchmark-smoke.json
```

Release gate dùng pipeline thật và DeepEval 4.1.0. Cần cấu hình
`DEMO_DOCUMENT_PATH`, `LLM_API_KEY`, `LLM_MODEL`, `OPENAI_API_KEY` và
`EVAL_JUDGE_MODEL`; judge mặc định là `gpt-5.4`, temperature 0.

```powershell
python -m pip install -r requirements-eval.txt
python -m evals.run --suite full --output evidence/benchmark.json
$env:PYTHONIOENCODING="utf-8" # cần cho Rich/DeepEval trên Windows
deepeval test run evals/tests
```

Dataset release ở `evals/datasets/demo_v1.jsonl`. Bộ deterministic tái sử dụng
`src/retrieval/golden.py`; không có evaluator golden thứ hai. Chế độ
`heuristic_fallback` chỉ giữ khả dụng runtime và không được phép qua release
gate. Thời gian judge không được tính vào latency của pipeline.

## Logging an toàn

- Backend chỉ log method, path, status, duration và content-length.
- Không log toàn văn tài liệu upload.
- Không log API key, token hoặc giá trị secret-like trong message.

## Quy tắc làm việc 48 giờ

- Chốt schema và API trước khi chia nhánh.
- Mỗi nhiệm vụ có điều kiện hoàn thành và bằng chứng chạy được.
- Merge theo lát cắt end-to-end; không chờ đến cuối mới tích hợp.
- Sau giờ 32 chỉ sửa lỗi P0/P1 và hoàn thiện demo.
