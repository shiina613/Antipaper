# Yêu cầu frontend Antipaper

**Phiên bản:** 2.0
**Phạm vi:** MVP/hackathon 48 giờ
**Nguồn ưu tiên:** [`problem.txt`](../problem.txt), sau đó là [`PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md) và [`API_CONTRACT.md`](API_CONTRACT.md)

Tài liệu này là đặc tả có thể dùng đồng thời cho thiết kế UI, phát triển frontend, tích hợp backend và nghiệm thu end-to-end. Mọi tính năng không có tiêu chí nghiệm thu rõ ràng dưới đây không được coi là hoàn thành.

## 1. Mục tiêu sản phẩm và định nghĩa thành công

Antipaper giúp lãnh đạo, cán bộ tham mưu và thư ký cuộc họp chuyển một tài liệu PDF/DOCX dài 40–60 trang thành một bộ thông tin có thể dùng ngay trong cuộc họp:

```text
Tải tài liệu
  → biết hệ thống đang xử lý đến đâu
  → đọc điểm cần quyết định và tác động
  → hiểu thuật ngữ/điều khoản quan trọng
  → chuẩn bị câu hỏi phản biện
  → kiểm chứng mọi nhận định bằng trang và excerpt nguồn
  → hỏi đáp tiếng Việt trong phạm vi tài liệu
  → mở lại phiên xử lý từ Lịch sử
```

Frontend giải quyết thành công bài toán khi người dùng có thể hoàn thành luồng trên mà không cần hiểu pipeline AI, không phải refresh thủ công và không bị trình bày dữ liệu giả như kết quả chính thức.

### 1.1 Các kết quả bắt buộc từ `problem.txt`

| Kết quả nghiệp vụ | Ngưỡng nghiệm thu | Cách frontend phải chứng minh |
|---|---:|---|
| Tài liệu đầu vào | PDF/DOCX công khai, từ 40 trang trở lên cho demo | Hiển thị tên file, dung lượng, số trang sau khi report sẵn sàng |
| Tóm tắt điều hành | Đủ bối cảnh, nội dung chính, điểm cần quyết định, tác động | Tab Tổng quan hiển thị đúng bốn nhóm `summary` |
| Thuật ngữ/điều khoản | Tối thiểu 10 mục có giải thích theo ngữ cảnh | Tab Thuật ngữ hiển thị số lượng, cảnh báo nếu dưới 10, citation cho từng mục |
| Câu hỏi phản biện | Tối thiểu 5 câu phù hợp với chính tài liệu | Tab Câu hỏi phản biện hiển thị câu hỏi, rationale, citation và hành động dùng câu hỏi |
| Văn bản liên quan | Hiển thị căn cứ được backend trả về, không tự tạo dữ liệu | Tab Văn bản liên quan hiển thị số hiệu, nguồn, lý do và citation; empty state nếu API trả rỗng |
| Kiểm chứng | Một thao tác từ nội dung đến trang/Điều/Khoản/excerpt | Citation chip mở citation drawer và tải page API theo nhu cầu |
| Hỏi đáp | Câu trả lời tiếng Việt có nguồn hoặc từ chối khi thiếu bằng chứng | Popup chat dùng `document_id` hiện tại, hiển thị `insufficient_evidence` và không tạo citation giả |
| Độ trễ | Backend từ nhận đủ file đến `completed` dưới 60 giây trong run hợp lệ | Hiển thị `elapsed_seconds` từ status API, không cộng thời gian cache hit vào benchmark |

Nếu một ngưỡng không đạt, frontend phải hiển thị trạng thái chất lượng chưa đạt; không được tự nhân bản, tự viết thêm hoặc che thiếu hụt bằng dữ liệu mẫu.

## 2. Truy vết từ vấn đề đến tính năng

| Vấn đề trong `problem.txt` | Nguyên nhân ở trải nghiệm | Tính năng bắt buộc | Bằng chứng pass |
|---|---|---|---|
| Tài liệu dài, người dùng chỉ có khoảng một ngày | Không biết nên đọc phần nào trước | Tổng quan ưu tiên điểm cần quyết định và tác động; header có metadata xử lý | Người dùng nhận ra điểm cần quyết định trước các chi tiết kỹ thuật |
| Nhiều thuật ngữ pháp lý/hành chính/kỹ thuật | Không hiểu ngữ cảnh của từ khóa | Tab Thuật ngữ với tối thiểu 10 mục, giải thích ngắn và citation | Mỗi mục mở được nguồn liên quan |
| Cuộc họp thiếu câu hỏi phản biện | Không có cấu trúc chuẩn bị thảo luận | Tab Câu hỏi phản biện với tối thiểu 5 câu, rationale và nút đưa vào chat | Câu hỏi được dùng trong popup mà không phải gõ lại |
| Phải giải thích lại căn cứ | Kết luận AI không kiểm chứng được | Citation chip và drawer nguồn | Trang, Điều/Khoản và excerpt hiển thị trong một thao tác |
| Câu hỏi ngoài tài liệu dễ dẫn tới bịa đặt | Không có trạng thái từ chối rõ ràng | Refuse-by-default trong chat | `insufficient_evidence=true` không có citation |
| Người dùng cần tra cứu lại phiên trước | Không có timeline task và tiêu đề tài liệu | Lịch sử nhóm theo `document_id`, hiển thị `display_name` và task timeline | Mở lại được report của task hoàn tất |

## 3. Người dùng và công việc cần hoàn thành

| Persona | Công việc | Thông tin ưu tiên |
|---|---|---|
| Lãnh đạo/chủ trì | Nắm nhanh vấn đề và điều hành thảo luận | Điểm cần quyết định, tác động, câu hỏi phản biện, căn cứ trực tiếp |
| Cán bộ tham mưu | Kiểm tra cơ sở, điều khoản và phương án | Nội dung chính, thuật ngữ, Điều/Khoản, văn bản liên quan |
| Thư ký cuộc họp | Tra cứu trong thời gian thực | Chat ngắn, citation đúng trang, tên tài liệu và lịch sử xử lý |

Frontend không được yêu cầu người dùng hiểu `stage`, model, OCR, YOLO, hash hoặc vector index để hoàn thành các công việc trên.

## 4. Nguyên tắc trải nghiệm bắt buộc

| Nguyên tắc | Quyết định thiết kế |
|---|---|
| Meeting-first | Nội dung cần quyết định, tác động và câu hỏi phản biện đứng trước thông tin pipeline. |
| Citation-first | Nhận định quan trọng luôn có citation chip có thể bấm; nguồn không được ẩn trong metadata. |
| Refuse-by-default | Thiếu bằng chứng là một trạng thái nghiệp vụ riêng, không phải lỗi hệ thống và không phải câu trả lời bình thường. |
| Human-verifiable | Từ report hoặc chat, người dùng mở được metadata và excerpt nguồn bằng tối đa một thao tác. |
| Không gây hiểu nhầm | Phân biệt rõ API thật, fallback demo, cache hit, đang xử lý, lỗi và thiếu bằng chứng. |
| Không suy diễn | Frontend chỉ render field backend trả về; không tự đặt trang, Điều, Khoản, URL hoặc văn bản liên quan. |
| Tiếng Việt chuẩn | UI, trạng thái, error, helper text và nội dung hệ thống dùng UTF-8, hiển thị đủ dấu. |

## 5. Phạm vi và mức ưu tiên

### 5.1 P0 — bắt buộc để giải quyết bài toán

- App shell có sidebar trái và ba mục chính: **Tải lên**, **Kết quả**, **Lịch sử**.
- Upload một PDF/DOCX, tối đa 25 MB, có kiểm tra file và trạng thái upload.
- Polling trạng thái xử lý và hiển thị stage, progress, elapsed time, cache/error.
- Trang Kết quả với bốn nhóm: Tổng quan, Thuật ngữ, Câu hỏi phản biện, Văn bản liên quan.
- Tối thiểu 10 thuật ngữ và 5 câu hỏi phản biện khi backend trả đủ dữ liệu; cảnh báo khi dưới ngưỡng.
- Citation chip, citation drawer và page API lazy-load.
- Popup chat bên phải của trang Kết quả, chỉ hỏi trong phạm vi tài liệu hiện tại.
- Loading, empty, partial, error, retry và insufficient-evidence states.
- Responsive desktop/tablet/mobile và keyboard navigation cho luồng cốt lõi.

### 5.2 P1 — cần hoàn thiện ngay sau vertical slice P0

- Lịch sử persistent theo `task_id`, nhóm theo `document_id`, có tiêu đề tài liệu, loại task, thời gian, trạng thái, cache và lỗi.
- Filter History theo `status`, `task_type`, thời gian; phân trang `limit/offset`.
- Khôi phục document/report hiện tại sau refresh bằng route hoặc session-safe storage.
- Copy câu trả lời/citation và tải JSON report nếu API cung cấp hành động phù hợp.
- Hiển thị `generation_mode` và `quality` theo contract khi backend trả về.

### 5.3 P2 — không chặn MVP

- PDF canvas, thumbnail và highlight bounding box.
- OCR PDF scan và nhận dạng bảng phức tạp.
- Virtualization cho report rất lớn.
- Export báo cáo trình bày, onboarding và analytics dashboard.

### 5.4 Ngoài phạm vi 48 giờ

- Đăng nhập, SSO, phân quyền production và quản lý người dùng.
- Workflow phê duyệt nhiều cấp, chữ ký số, văn thư và lưu trữ hồ sơ production.
- Web search, tìm kiếm toàn kho, chỉnh sửa nội dung AI hoặc tự ra quyết định hành chính.
- Cam kết hỗ trợ mọi PDF scan/bảng phức tạp khi backend chưa cung cấp OCR/canvas/bounding box.

## 6. Kiến trúc thông tin và điều hướng

### 6.1 Ba mục navigation toàn cục

Navigation xuất hiện trên mọi màn hình, nằm ở sidebar trái, có thể thu gọn trên desktop và mở thành drawer trên mobile.

| Mục | Route logic | Khả dụng | Mục đích |
|---|---|---|---|
| **Tải lên** | `/` hoặc `/documents/new` | Luôn bật | Chọn file mới, kiểm tra và bắt đầu phân tích. |
| **Kết quả** | `/documents/{document_id}` | Bật khi có document hiện tại | Hiển thị tiến độ nếu chưa hoàn tất; hiển thị report nếu `completed`. |
| **Lịch sử** | `/history` | Luôn bật khi History API được triển khai | Theo dõi và mở lại các phiên upload/Q&A. |

Không đặt các mục sau thành navigation toàn cục: Thuật ngữ, Câu hỏi phản biện, Văn bản liên quan, Citation và Chat. Đây là các phần của Kết quả hoặc lớp tương tác theo ngữ cảnh.

### 6.2 Các tab bên trong Kết quả

Khi report hoàn tất, Kết quả có bốn tab nội dung:

| Tab | Nội dung bắt buộc | Không chứa |
|---|---|---|
| **Tổng quan** | Bối cảnh, nội dung chính, điểm cần quyết định, tác động | Chi tiết pipeline hoặc toàn bộ lịch sử chat |
| **Thuật ngữ** | Tối thiểu 10 thuật ngữ/điều khoản, giải thích theo ngữ cảnh, citation | Định nghĩa web hoặc kiến thức ngoài tài liệu |
| **Câu hỏi phản biện** | Tối thiểu 5 câu, rationale, citation, “Dùng câu hỏi này” | Cửa sổ chat đầy đủ |
| **Văn bản liên quan** | Title, document number, source, reason, citation | URL/trạng thái pháp lý frontend tự tạo |

Chat là popup cố định ở góc phải trang Kết quả, không phải tab thứ năm. Citation là drawer dùng chung, không phải navigation item.

### 6.3 Trạng thái navigation

| Trạng thái | Tải lên | Kết quả | Lịch sử | Tab Kết quả |
|---|---:|---:|---:|---|
| Chưa có tài liệu | Bật | Tắt | Bật | Ẩn |
| Đang upload | Đang chạy, khóa submit lặp | Tắt | Bật | Ẩn |
| `queued`/`processing` | Bật | Bật, hiển thị tiến độ | Bật | Ẩn |
| `completed` | Bật | Bật | Bật | Hiển thị đủ 4 tab và chat popup |
| `failed` | Bật | Bật, hiển thị lỗi/retry | Bật | Ẩn |
| Đang xem History | Bật | Bật nếu có tài liệu hiện tại | Active | Không tự mở report mới |

### 6.4 Bố cục theo phong cách Quiet Executive

- Nền ứng dụng ngà `#FAFAF4`; sidebar `#EEEEE9`; card trắng viền mảnh.
- Primary action dùng đen; olive `#566340` dành cho citation/trạng thái hỗ trợ; cảnh báo processing có thể dùng brass `#A77A32`.
- Font nội dung là Be Vietnam Pro; metadata kỹ thuật dùng Space Mono.
- Shadow nhẹ, radius 8–12px, không dùng gradient hoặc animation trang trí trong luồng nghiệp vụ.
- Desktop: sidebar trái, nội dung đọc tối đa khoảng 900px; citation drawer mở từ phải khi được kích hoạt.
- Mobile: sidebar thành drawer; tab Kết quả cuộn ngang hoặc xếp card; citation drawer thành full-screen/bottom sheet; chat popup không che ô nhập chính.

## 7. Yêu cầu chức năng chi tiết

### FE-01 — App shell và navigation

**Mục tiêu:** người dùng luôn biết mình đang ở Tải lên, Kết quả hay Lịch sử.

- Sidebar có logo Antipaper, ba mục chính, active state, disabled state và nút thu gọn/mở rộng.
- Mục Kết quả bị khóa khi chưa có `document_id`, tooltip giải thích lý do.
- Khi chọn mục trên mobile, drawer đóng và focus chuyển tới heading của view mới.
- Khi sidebar thu gọn, icon vẫn có tooltip/title và active state không chỉ dựa trên màu.
- Không có các mục marketing, settings giả hoặc kỹ thuật pipeline trong navigation MVP.

**Acceptance:** từ mọi trạng thái, người dùng chuyển được giữa ba view mà không tạo upload mới; active state và tiêu đề view nhất quán.

### FE-02 — Tải tài liệu

- Dropzone hỗ trợ chọn file hoặc kéo thả một file.
- Chỉ chấp nhận PDF/DOCX, tối đa 25 MB; validate extension, MIME nếu có và dung lượng ở client.
- Hiển thị tên file, loại, dung lượng, lỗi cụ thể và nút “Bắt đầu phân tích”.
- Không upload tự động khi vừa chọn file; khóa submit trong lúc request chạy.
- Khi nhận response upload, phải giữ `document_id`, `task_id` nếu có, `status`, `cached`.
- `cached=true` phải được hiển thị là cache hit nhưng vẫn coi là một task run riêng.
- Preview/mock chỉ là công cụ trình diễn có nhãn rõ; không được trộn với luồng API thật hoặc bằng chứng nghiệm thu.

**Acceptance:** file sai không tạo network request; file hợp lệ chuyển sang Kết quả/processing; double-submit không tạo hai task do frontend.

### FE-03 — Processing và polling

- Poll `GET /api/v1/documents/{document_id}/status` ngay sau upload và theo chu kỳ khoảng 1–2 giây.
- Hiển thị `status`, `stage`, `progress`, `elapsed_seconds`, `error`.
- Mapping nhãn stage do frontend kiểm soát; stage lạ hiển thị “Đang xử lý tài liệu”, không crash.
- Dừng polling khi `completed`, `failed`, đổi document, unmount hoặc request bị huỷ.
- Chỉ gọi report sau `status=completed`; không suy diễn hoàn tất từ `progress=100`.
- Khi vượt 60 giây, cảnh báo trễ mục tiêu nhưng không tự hủy job.
- Lỗi mạng tạm thời hiển thị “Đang kết nối lại”/retry; không tự chuyển thành failed nếu backend chưa trả failed.

**Acceptance:** người dùng thấy tiến trình liên tục; report tự mở sau completed; report không bị gọi lặp trong một run bình thường.

### FE-04 — Kết quả và metadata

- Header hiển thị `file_name`, `page_count`, `processing_seconds` và status.
- Hiển thị cache hit nếu thông tin upload/history cho biết.
- Nếu `generation_mode` có trong API:
  - `llm`: “Báo cáo AI có kiểm tra nguồn”.
  - `heuristic_fallback`: cảnh báo “Kết quả dự phòng; cần kiểm tra kỹ”.
- Nếu `quality` có trong API, chỉ render các field đã chốt; field thiếu/null không làm hỏng trang.
- Có nút quay lại Tải lên để bắt đầu tài liệu mới.
- Không đưa hash, model name hoặc log pipeline vào nội dung chính.

### FE-05 — Tổng quan có cấu trúc

Render đúng thứ tự: `decision_points`, `context`, `main_content`, `impact`.

Mỗi nhóm summary:

- Backend trả một hoặc nhiều item theo từng chủ đề; tổng bốn nhóm tối đa 800 từ và frontend hiển thị mỗi item thành một gạch đầu dòng.
- Hiển thị toàn bộ `text` hoặc collapse có thể mở lại, không cắt mất ý.
- Gom mọi `citation_id` hợp lệ vào nút “Nguồn tóm tắt”; khi mở drawer phải hiển thị từng đoạn nguồn và bản xem trang gốc của mọi trang liên quan.
- Nếu không có citation, hiển thị cảnh báo “Chưa có nguồn xác thực”, không âm thầm coi là tin cậy.
- Điểm cần quyết định phải có ưu tiên thị giác cao nhất.
- Empty section phải nêu rõ backend không trả nội dung; không chèn placeholder giả.

### FE-06 — Thuật ngữ/điều khoản

- Hiển thị số lượng và cảnh báo khi dưới 10 mục.
- Mỗi item có `term`, `explanation`, citation list và trạng thái nguồn.
- Giải thích phải nằm ngay trong tab, hỗ trợ quét nhanh bằng card/list hoặc accordion.
- Không dùng web search hoặc kiến thức ngoài tài liệu để bù giải thích.
- Citation mở cùng drawer dùng cho toàn app.

### FE-07 — Câu hỏi phản biện

- Hiển thị rõ từng câu, số thứ tự, `rationale` và citations.
- Tối thiểu 5 mục là ngưỡng chất lượng; dưới ngưỡng phải cảnh báo.
- Nút “Dùng câu hỏi này” chỉ điền vào chat popup, không tự gửi request.
- Câu hỏi phải giữ nguyên thứ tự backend và không bị rút gọn gây mất nghĩa.
- Không tạo câu hỏi mới ở frontend để bù số lượng.

### FE-08 — Văn bản liên quan

- Hiển thị `title`, `document_number`, `source`, `reason`, citations.
- Mapping nhãn `cited_in_document` thành tiếng Việt dễ hiểu.
- Nếu mảng rỗng, hiển thị empty state có giải thích.
- Không tự tạo URL, số hiệu, ngày hiệu lực hoặc nhận định pháp lý mà backend không trả.

### FE-09 — Citation và viewer nguồn

- Resolve chip qua `report.citations[citation_id]`; ID không tồn tại phải fail-closed.
- Chip hiển thị tối thiểu `Trang {page}`; drawer hiển thị thêm chapter/article/clause/excerpt nếu có.
- Bấm chip mở drawer trong một thao tác; excerpt metadata hiển thị ngay trước khi page API hoàn tất.
- Lazy-load `GET /documents/{document_id}/pages/{page_number}`; không tải toàn bộ pages khi mở report.
- Loading page không xóa excerpt đã có; page error có retry độc lập.
- Drawer phải có close, focus return, keyboard support và responsive full-screen/bottom sheet.
- MVP chỉ cam kết text/blocks/excerpt; không cam kết PDF canvas, thumbnail hoặc bounding-box highlight khi API chưa cung cấp.

### FE-10 — Chat popup theo kết quả hiện tại

- Chỉ hiển thị khi report của document hiện tại đã `completed`.
- Popup nằm bên phải trang Kết quả; có trạng thái collapsed thành nút “Hỏi về kết quả”.
- Header popup phải nêu rõ phạm vi: chỉ hỏi về tóm tắt, thuật ngữ, câu hỏi phản biện, văn bản liên quan và căn cứ của tài liệu hiện tại.
- Có textarea, submit button, loading, retry/error, copy answer và citation chips.
- Câu hỏi gợi ý từ `suggested_questions` có thể điền sẵn nhưng không tự gửi.
- Gửi `POST /documents/{document_id}/questions` với câu hỏi đã trim.
- Khi `insufficient_evidence=true`, hiển thị “Không đủ bằng chứng trong tài liệu”, giữ `answer`, không render citation.
- Không tìm web, không trả lời kiến thức ngoài tài liệu và không hiển thị chat khi chưa có report.
- Chat history chỉ là state của phiên UI; API hiện không có `conversation_id`, không được giả định memory dài hạn.

### FE-11 — Lịch sử task

- Gọi `GET /api/v1/history?limit=&offset=&status=&task_type=` với filter đang chọn.
- Dùng đúng `task_type` backend: `document_processing` hoặc `question_answer`.
- Nhóm các item có cùng `document_id` thành một session; tên session ưu tiên `display_name` của task upload.
- Hiển thị timeline gồm loại task, display name/câu hỏi, created time, status, stage, progress, duration, cached và error.
- Tác vụ `question_answer` phải hiển thị câu hỏi độc lập trong timeline của tài liệu.
- Task document hoàn tất có `document_id` cho phép “Mở báo cáo”; task lỗi chỉ cho xem lỗi/retry phù hợp.
- Thời gian hiển thị theo Asia/Bangkok trong demo, giữ ISO timestamp để xử lý.
- Không lưu toàn văn tài liệu hoặc câu trả lời đầy đủ vào History UI/localStorage ngoài dữ liệu API cần render.

### FE-12 — Error, loading, empty và partial states

| State | Yêu cầu |
|---|---|
| Upload invalid/too large | Lỗi cạnh dropzone, không gửi request |
| Upload/network error | Lỗi rõ, retry theo `retryable`, không mất file nếu browser còn giữ |
| Processing | Progress, stage, elapsed và action tiếp theo |
| Processing failed | Error code/message, retry nếu được phép, tạo tài liệu mới |
| Report loading | Skeleton theo nhóm nội dung, không số liệu giả |
| Section empty | Empty state riêng, không làm mất các section khác |
| Citation invalid | Không gọi page API, hiển thị nguồn không hợp lệ |
| Page error | Giữ report/excerpt, retry viewer độc lập |
| Q&A loading | Giữ câu hỏi, khóa gửi lặp |
| Q&A insufficient evidence | Trạng thái từ chối riêng, citation list rỗng |
| History error | Giữ filter, hiển thị retry, không thay bằng lịch sử giả |

## 8. Hợp đồng tích hợp frontend–backend

Base URL là `/api/v1`; upload dùng `multipart/form-data`; các API khác dùng JSON UTF-8.

| Nhu cầu | Endpoint | Field phải giữ |
|---|---|---|
| Upload | `POST /documents` | `document_id`, `task_id`, `status`, `cached` |
| Poll | `GET /documents/{document_id}/status` | `status`, `stage`, `progress`, `elapsed_seconds`, `error` |
| Report | `GET /documents/{document_id}/report` | report, `generation_mode`, `quality` nếu có |
| Q&A | `POST /documents/{document_id}/questions` | `answer`, `insufficient_evidence`, `citation_ids`, `latency_ms`, `task_id` |
| Page | `GET /documents/{document_id}/pages/{page_number}` | `page_number`, `text`, `blocks` |
| History list | `GET /history` | `items`, `total`, `limit`, `offset` |
| History detail | `GET /history/{task_id}` | task state hiện tại |

Frontend phải bám các Pydantic schemas hiện có. Các list có thể rỗng; `chapter`, `article`, `clause`, `task_id`, `quality` và error có thể null/optional. Không đổi tên field hoặc tự thêm field chưa có contract.

**Lưu ý tích hợp:** backend định nghĩa `TaskType` là `document_processing | question_answer`. Client dùng literal khác như `question_answering` là lỗi contract và phải được sửa trước nghiệm thu History.

## 9. Quản lý trạng thái và độ tin cậy

| State | Nguồn sự thật | Quy tắc |
|---|---|---|
| File trước upload | Browser File | Chỉ local, không log bytes |
| Document hiện tại | `document_id` | Mọi status/report/page/question phải gắn cùng ID |
| Processing | Status API | Một polling loop, huỷ khi đổi document/unmount |
| Report | Report API | Chỉ set sau `completed`, không ghi đè bởi response document cũ |
| Citation | UI + page API | Invalid ID fail-closed; viewer lỗi không làm mất report |
| Chat | Question API + session state | Khóa submit khi pending; không giả định backend conversation memory |
| History | History API + `X-User-ID` | Không dùng local mock thay API thật trong luồng chính |

Phải chống race condition khi người dùng upload liên tiếp hoặc bấm mở hai citation liên tiếp. Response cũ không được ghi đè state của document/citation mới.

## 10. Yêu cầu phi chức năng

### 10.1 Performance

- Phản hồi visual cho click/input dưới khoảng 100 ms.
- Chỉ tải page khi mở citation; không preload toàn bộ document pages.
- Poll khoảng 1–2 giây, không tạo nhiều loop cho cùng document.
- Không render toàn bộ nội dung lớn nếu có thể dùng collapse/list virtualization.
- Hiển thị elapsed time backend và tách cache hit khỏi benchmark xử lý chính.

### 10.2 Reliability

- Abort hoặc ignore mọi request cũ khi đổi document.
- Viewer, chat và History lỗi độc lập, không làm mất report.
- Retry có giới hạn và chỉ bật khi `retryable=true` hoặc lỗi mạng tạm thời.
- Demo chính chạy liên tiếp ba lần không có lỗi P0/P1.

### 10.3 Security và privacy

- Không log file bytes, toàn văn, answer đầy đủ, API key hoặc token.
- Không đưa secret vào client bundle.
- Sanitize nội dung backend trước khi render HTML/Markdown.
- Demo phải dùng tài liệu công khai hoặc đã được phê duyệt.
- `X-User-ID` chỉ là phân vùng demo, không phải authentication.

### 10.4 Accessibility

- Upload, sidebar, tab, chat, citation drawer và History dùng được bằng keyboard.
- Active nav/tab có semantic `aria-current`/`aria-selected` và focus rõ.
- Dialog có label, đóng bằng nút rõ ràng và trả focus về trigger.
- Màu không phải tín hiệu duy nhất cho success/warning/error/fallback.
- Contrast tối thiểu WCAG AA.

### 10.5 Responsive và localization

- Desktop từ 1280px: sidebar và vùng đọc ổn định; drawer citation mở từ phải.
- Tablet 768–1279px: report một cột, chat/citation thu gọn hoặc drawer.
- Mobile 360–767px: sidebar drawer, chat không vượt viewport, citation full-screen/bottom sheet.
- UI mặc định tiếng Việt; timestamp hiển thị Asia/Bangkok trong demo; file name dài có tooltip.

## 11. Kịch bản nghiệm thu end-to-end

### 11.1 Happy path

1. Mở ứng dụng ở mục Tải lên và thấy định dạng PDF/DOCX cùng giới hạn 25 MB.
2. Chọn một tài liệu công khai tối thiểu 40 trang.
3. Bấm phân tích một lần; UI chuyển sang Kết quả/processing.
4. Thấy `queued/processing`, stage, progress và elapsed time; không refresh thủ công.
5. Khi completed dưới 60 giây, report mở ở Tổng quan.
6. Kiểm tra bốn nhóm summary và điểm cần quyết định.
7. Mở Thuật ngữ, xác nhận tối thiểu 10 mục hoặc cảnh báo thiếu ngưỡng.
8. Mở Câu hỏi phản biện, xác nhận tối thiểu 5 câu hoặc cảnh báo thiếu ngưỡng.
9. Bấm citation từ summary/term/question; drawer hiển thị trang, Điều/Khoản và excerpt.
10. Bấm “Dùng câu hỏi này”; popup chat mở và điền câu hỏi nhưng chưa tự gửi.
11. Gửi câu hỏi có bằng chứng; nhận answer tiếng Việt, latency và citation.
12. Gửi câu hỏi ngoài phạm vi; thấy thông báo thiếu bằng chứng, không có citation giả.
13. Mở Lịch sử; thấy tài liệu, tiêu đề, task upload và task question tương ứng.
14. Mở lại task document hoàn tất và trở về report.

### 11.2 Negative path

- File không phải PDF/DOCX.
- File lớn hơn 25 MB.
- Backend unavailable hoặc timeout.
- Job trả failed.
- Report section rỗng.
- Citation ID không có trong `citations`.
- Page API lỗi trong khi report vẫn đọc được.
- Q&A trả `insufficient_evidence=true`.
- Upload lại cùng file tạo cache hit nhưng task history mới.
- History filter không có item.
- Hai upload/citation request chạy gần đồng thời.

### 11.3 Definition of Done

Feature chỉ được đánh dấu hoàn thành khi:

- API thật hoặc mock đúng contract được dùng; mock phải có nhãn và không nằm trong luồng chính.
- Có happy, loading, empty, partial, error và retry state.
- Có keyboard/responsive check cơ bản.
- Không có hard-coded report trong production path.
- Citation invalid fail-closed và citation hợp lệ mở đúng metadata/excerpt.
- Q&A từ chối rõ khi thiếu bằng chứng.
- History dùng đúng `question_answer` và hiển thị tên tài liệu/task timeline.
- `npm run lint` và `npm run build` pass.
- Có checklist hoặc ảnh/video chứng minh happy path và negative path.

## 12. Bằng chứng nghiệm thu và thứ tự triển khai

### 12.1 Bằng chứng cần thu thập

- Screenshot upload, processing, completed report và History.
- Video/capture một thao tác citation mở đúng excerpt.
- Capture một Q&A có citation và một Q&A bị từ chối.
- Log không chứa file bytes, token hoặc toàn văn nhạy cảm.
- Bảng đo `processing_seconds`, page count, cache status và generation mode nếu API trả.

### 12.2 Vertical slices

| Thứ tự | Slice | Điều được chứng minh |
|---:|---|---|
| 1 | Sidebar + upload + API client + polling | Người dùng bắt đầu và theo dõi được job |
| 2 | Kết quả Tổng quan + metadata | Người dùng nắm điểm quyết định trong vài phút |
| 3 | Thuật ngữ + câu hỏi phản biện + văn bản liên quan | Người dùng chuẩn bị được nội dung họp |
| 4 | Citation drawer + page API | Nhận định có thể kiểm chứng |
| 5 | Chat popup + insufficient evidence | Q&A grounded và refuse-by-default |
| 6 | History + refresh/race/error + responsive | Luồng demo có khả năng phục hồi và mở lại |

### 12.3 Quyết định mở rộng cần backend chốt trước

1. Muốn highlight đúng tọa độ PDF phải bổ sung binary/page image/bounding box.
2. Muốn mục rủi ro riêng phải bổ sung field report, không suy diễn từ `impact`.
3. Muốn hội thoại nhiều lượt phải bổ sung `conversation_id` và schema conversation.
4. Muốn mở văn bản liên quan bên ngoài phải bổ sung URL chính thức, ngày ban hành và hiệu lực.
5. Trước production phải thay `X-User-ID` bằng identity đã xác thực, bổ sung SSO, phân quyền, audit log và retention policy.
