# Ngăn xếp công nghệ cho 48 giờ

## 1. Công nghệ chốt

| Lớp | Công nghệ | Lý do |
|---|---|---|
| Giao diện | Next.js 16, TypeScript, Tailwind/shadcn | Kho mã đã có UI; đủ nhanh để làm dashboard và viewer |
| Máy chủ API | Python 3.11, FastAPI, Pydantic, Uvicorn | Hợp đồng API rõ, tích hợp tốt với luồng AI |
| PDF | PyMuPDF | Trích xuất nhanh, giữ số trang và block vị trí |
| Word | python-docx | Đủ cho DOCX native trong phạm vi demo |
| Bảng PDF native | `PyMuPDF Page.find_tables()` | Lấy ô/hàng/cột trực tiếp, xuất Markdown mà không render ảnh |
| Bảng ảnh/scan | YOLOv8 table-specific hiện có | Chỉ phát hiện/crop bảng `bordered` và `borderless`; không nhận dạng nội dung |
| Runtime GPU | PyTorch CUDA 12.6 + Ultralytics | Chạy inference YOLOv8 trên GPU của máy demo |
| AI | SDK LLM trực tiếp, model cấu hình qua biến môi trường | Tránh khóa model và giảm abstraction |
| Truy hồi | Embedding API + cosine similarity trong RAM | Dữ liệu một tài liệu nhỏ; không cần vector database |
| Văn bản liên quan | Regex số hiệu/căn cứ + catalog JSON cục bộ | Nguồn kiểm soát được, dễ demo và có thể giải thích |
| Bộ nhớ đệm | Thư mục artifact theo SHA-256 + job store in-memory | Không cần Redis/database trong hackathon |
| Kiểm thử | pytest, frontend lint/build, checklist E2E | Nhanh, đủ bằng chứng nghiệm thu |
| Trình diễn dự phòng | Streamlit | Đã có khung; dùng nếu Next.js chưa ổn trước giờ 32 |

## 2. Gói phụ thuộc nên có

Backend tối thiểu:

```text
fastapi
uvicorn[standard]
pydantic
python-multipart
pymupdf
python-docx
numpy
httpx
python-dotenv
pytest
```

Thêm SDK chính thức của nhà cung cấp LLM sau khi chốt API key. Không thêm LangChain, Chroma/FAISS, Celery hoặc Redis trong luồng bắt buộc.

YOLOv8 GPU trên máy Windows/Python 3.12:

```text
ultralytics
torch               # CUDA wheel phải khớp driver/runtime
torchvision
```

Checkpoint `models/table_detect_yolov8.pt` là bắt buộc. Không fallback sang weight COCO chung vì các class đó không đại diện cho bảng.

## 3. Chiến lược đọc bảng

```text
Trang PDF
  ├─ Có text/vector lines → PyMuPDF find_tables() → Markdown/JSON
  └─ Bảng dạng ảnh/scan
       └─ YOLOv8 table-specific → bbox + confidence + class + crop ảnh
```

Mỗi detection phải giữ `page`, `bbox`, confidence và class. YOLOv8 không cung cấp số hàng/cột, nội dung ô hoặc Markdown/JSON.

## 4. Thành phần giữ nhưng không bắt buộc

| Thành phần cũ | Quyết định |
|---|---|
| YOLO/Ultralytics | Thành phần duy nhất cho bảng ảnh; contract giới hạn ở detection/crop |
| OpenCV/pdf2image | Chỉ dùng nếu triển khai OCR/table fallback |
| Streamlit | Giữ làm phương án demo dự phòng |
| Logic rule-based | Giữ làm fallback khi LLM lỗi; không dùng làm kết quả chấm chính |

## 5. Biến môi trường

```text
LLM_API_KEY=
LLM_MODEL=
LLM_BASE_URL=
EMBEDDING_MODEL=
MAX_LLM_CONCURRENCY=5
MAX_FILE_MB=25
ARTIFACT_DIR=.artifacts
FRONTEND_ORIGIN=http://localhost:3000
ENABLE_TABLE_DETECTION=true
TABLE_YOLO_DEVICE=0
```

Không commit `.env`, API key, output tài liệu hoặc log chứa toàn văn.

## 6. Nguyên tắc dùng LLM

- Model phải hỗ trợ tiếng Việt, JSON/schema output và context đủ cho batch 6–8 trang.
- Prompt yêu cầu trả `chunk_id`, không yêu cầu model tự viết số trang.
- Map calls chạy song song có semaphore; reduce chỉ chạy sau khi map hợp lệ.
- Timeout rõ ràng, retry tối đa một lần và có fallback rule-based.
- Chốt model trước giờ 2; không đổi model sau giờ 24 nếu không có lỗi P0.

## 7. Môi trường chuẩn

- Python 3.11; không dùng Python 3.14 cho môi trường thi vì rủi ro tương thích package.
- Node.js 20 LTS.
- Một lệnh chạy backend và một lệnh chạy frontend; không yêu cầu dịch vụ ngoài ngoài LLM API.
- Ghi phiên bản package vào lock file sau khi luồng đầu tiên chạy ổn.
