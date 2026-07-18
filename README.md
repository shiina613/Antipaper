# Antipaper

Trợ lý AI giúp cán bộ đọc nhanh tài liệu họp dài, chuẩn bị câu hỏi và tra cứu bằng tiếng Việt với citation đến trang/mục/điều.
<img width="1939" height="4097" alt="mermaid-diagram-2026-07-18-075329" src="https://github.com/user-attachments/assets/e50b2b98-9fe2-4cdd-8f85-1cd4eb7334f0" />

## Trạng thái hiện tại

Kho mã nguồn đang ở mức khung kỹ thuật:

- Đã có luồng PDF bằng PyMuPDF, Streamlit MVP và giao diện Next.js tĩnh.
- Đã có xử lý mẫu cho tóm tắt, thuật ngữ, câu hỏi và Q&A cấp trang.
- Chưa có LLM thật, DOCX, FastAPI, truy hồi ngữ nghĩa, citation cấp điều/mục và đo hiệu năng dưới 60 giây.
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
├── data/                 # PDF mẫu công khai
├── docs/                 # Kiến trúc, kế hoạch, kiểm thử và task
├── frontend/             # Next.js dashboard
├── scripts/              # Script demo/benchmark
├── src/intelligence/     # Tóm tắt, thuật ngữ, câu hỏi, Q&A
├── src/pipeline/         # Trích xuất và chuẩn hóa tài liệu
└── app.py                # Streamlit MVP dự phòng
```

## Chạy baseline hiện tại

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python download_yolo_table_weights.py
streamlit run app.py
```

Baseline cần YOLO weights. Kiến trúc hackathon mới sẽ đưa YOLO ra khỏi luồng bắt buộc để ưu tiên tốc độ và độ ổn định.

Frontend tĩnh:

```powershell
cd frontend
npm install
npm run dev
```

## Quy tắc làm việc 48 giờ

- Chốt schema và API trước khi chia nhánh.
- Mỗi nhiệm vụ có điều kiện hoàn thành và bằng chứng chạy được.
- Merge theo lát cắt end-to-end; không chờ đến cuối mới tích hợp.
- Sau giờ 32 chỉ sửa lỗi P0/P1 và hoàn thiện demo.
