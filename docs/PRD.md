# PRD — Antipaper

**Trạng thái:** Baseline v1  
**Phạm vi:** Hackathon 48 giờ và định hướng thí điểm UBND cấp tỉnh  
**Nguồn yêu cầu:** `problem.txt` và hiện trạng repository

## 1. Context

### 1.1 Bối cảnh nghiệp vụ

Tài liệu chuẩn bị họp thường dài 40–60 trang, chứa thuật ngữ pháp lý, hành chính và kỹ
thuật. Lãnh đạo, cán bộ tham mưu và thư ký thường chỉ nhận tài liệu trước cuộc họp
khoảng một ngày. Hệ quả là thời gian chuẩn bị không đủ, cuộc họp phải giải thích lại
tài liệu, câu hỏi phản biện chưa sắc và điểm cần quyết định chưa được tách rõ.

Antipaper chuyển PDF/DOCX thành một báo cáo chuẩn bị họp có cấu trúc, có thể truy
ngược mọi nhận định quan trọng về đúng bằng chứng gốc, đồng thời cung cấp hỏi đáp
tiếng Việt theo nguyên tắc thiếu bằng chứng thì từ chối.

### 1.2 Tuyên bố giá trị

> Trong chưa đầy 60 giây đối với tài liệu demo công khai từ 40 trang, người tham dự
> nhận được bản chuẩn bị họp có cấu trúc, ít nhất 10 thuật ngữ, ít nhất 5 câu hỏi phản
> biện và Q&A dẫn nguồn; nhờ đó thời gian đọc giảm nhưng khả năng kiểm chứng không giảm.

### 1.3 Người dùng và Jobs-to-be-Done

| Persona | Công việc cần hoàn thành | Rủi ro cần giảm |
|---|---|---|
| Lãnh đạo/chủ trì | Nắm bối cảnh, điểm cần quyết định và tác động trước cuộc họp | Quyết định khi chưa thấy đủ căn cứ hoặc hệ quả |
| Cán bộ tham mưu | Kiểm tra căn cứ, phát hiện khoảng trống, chuẩn bị câu hỏi phản biện | Bỏ sót điều kiện, trách nhiệm, thời hạn hoặc xung đột |
| Thư ký cuộc họp | Tra cứu nhanh đúng trang/mục/điều và ghi nhận đầu việc | Mất thời gian lật tài liệu, dẫn sai nguồn |
| Quản trị viên pilot | Kiểm soát người dùng, dữ liệu, cấu hình và audit | Lộ lọt tài liệu hoặc không truy vết được thao tác |

### 1.4 Nguyên tắc sản phẩm

1. **Grounded by default:** nhận định quan trọng phải liên kết tới evidence ID hợp lệ.
2. **Fail closed:** thiếu bằng chứng, citation sai hoặc parser không đáng tin cậy thì
   hiển thị giới hạn và từ chối kết luận, không suy đoán.
3. **Source before synthesis:** metadata trang/mục/điều do parser tạo; LLM chỉ được chọn
   ID từ whitelist, không được tạo metadata nguồn.
4. **Privacy by deployment:** tài liệu nội bộ không rời trust boundary khi chưa có phê
   duyệt bằng văn bản.
5. **Meeting utility:** đầu ra phải hỗ trợ hiểu, phản biện và quyết định; bản tóm tắt
   chung chung dù đúng ngữ pháp vẫn không đạt.

## 2. Problem Statement

### 2.1 Vấn đề cốt lõi

| Vấn đề | Nguyên nhân gốc | Hậu quả |
|---|---|---|
| Quá tải đọc | Tài liệu dài, thời gian chuẩn bị ngắn | Hiểu không đồng đều giữa người họp |
| Khó kiểm chứng | Tóm tắt thủ công không gắn citation cấp trang/điều | Mất niềm tin và tốn thời gian đối chiếu |
| Phản biện yếu | Không tách rõ giả định, tác động, trách nhiệm, thời hạn | Cuộc họp thiên về giải thích thay vì ra quyết định |
| Tra cứu chậm | Tìm kiếm thủ công trong nhiều trang | Gián đoạn thảo luận |
| Rủi ro AI | Mô hình có thể thêm kiến thức ngoài nguồn hoặc bịa citation | Sai lệch pháp lý và rủi ro dữ liệu |

### 2.2 Mục tiêu

| ID | Mục tiêu | Chỉ báo |
|---|---|---|
| OBJ-01 | Rút ngắn thời gian tạo bản chuẩn bị họp | E2E processing `< 60 giây` cho tài liệu demo hợp lệ |
| OBJ-02 | Tăng khả năng kiểm chứng | 100% nhận định quan trọng có citation hợp lệ |
| OBJ-03 | Tạo đầu ra đủ dùng trong cuộc họp | ≥10 thuật ngữ đúng ngữ cảnh; ≥5 câu hỏi phản biện đạt rubric |
| OBJ-04 | Hỏi đáp an toàn | Câu trả lời đúng nguồn; ngoài phạm vi phải từ chối |
| OBJ-05 | Chuẩn bị được cho pilot | Có kiến trúc, nguồn dữ liệu, kiểm soát bảo mật và roadmap UBND |

### 2.3 Không phải mục tiêu

Trong hackathon không huấn luyện mô hình riêng, không triển khai workflow phê duyệt
nhiều cấp, không xây hạ tầng phân tán, không tích hợp hệ thống văn thư thật. OCR,
nhận dạng bảng bằng vision, đăng nhập, RBAC và tìm kiếm toàn kho là hậu MVP, trừ khi
cần làm hardening tối thiểu cho pilot.

## 3. Technical Deep-Dive

### 3.1 Phạm vi theo giai đoạn

| Năng lực | Hackathon bắt buộc | Pilot UBND | Production |
|---|---:|---:|---:|
| PDF native | Có | Có | Có |
| DOCX cơ bản | Có | Có, cần cải thiện định vị nguồn | Có |
| Tóm tắt 4 phần | Có | Có | Có |
| ≥10 thuật ngữ có nguồn | Có | Có | Có |
| ≥5 câu hỏi phản biện | Có | Có | Có |
| Văn bản liên quan | Có | Nguồn chính thống/allowlist | Kho pháp lý được quản trị |
| Q&A tiếng Việt + từ chối | Có | Có | Có |
| Citation mở về nguồn | Có | Có | Có |
| Đo hiệu năng/quality | Có | Dashboard vận hành | SLO và cảnh báo |
| OCR PDF scan | Không | Thử nghiệm có confidence | Có theo chính sách |
| Auth/RBAC | Không | Bắt buộc | Bắt buộc + federation |
| Tìm kiếm toàn kho | Không | Tùy pilot | Có nếu được phê duyệt |

### 3.2 Yêu cầu chức năng

#### 3.2.1 Nạp và xử lý tài liệu

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| FR-ING-01 | Nhận một file PDF hoặc DOCX mỗi tác vụ | Từ chối extension/type không hỗ trợ với lỗi có mã; giới hạn hiện tại 25 MB |
| FR-ING-02 | Mỗi upload là một tác vụ mới | Hai file giống byte vẫn có `document_id` khác nhau; không tái dùng kết quả ngầm |
| FR-ING-03 | Trích xuất PDF native theo trang | Trang hiển thị và citation dùng page number 1-based của file gốc |
| FR-ING-04 | Trích xuất DOCX cơ bản | Đọc paragraph và table; UI phải công khai giới hạn định vị trang của DOCX |
| FR-ING-05 | Phát hiện cấu trúc pháp lý | Khi nguồn có Chương/Mục/Điều/Khoản/Điểm, metadata được gắn vào chunk bằng parser |
| FR-ING-06 | Công khai trạng thái xử lý | Client quan sát được queued, processing, completed hoặc failed cùng stage/progress |
| FR-ING-07 | Không xử lý scan như native text | Nếu mật độ text quá thấp, cảnh báo “cần OCR/không hỗ trợ”, không tạo báo cáo gây hiểu nhầm |

Lưu ý: “tài liệu công khai thật từ 40 trang” là điều kiện của kịch bản nghiệm thu
hackathon, không nên là hard validation cho mọi upload vì người dùng vẫn có nhu cầu
với tài liệu ngắn.

#### 3.2.2 Báo cáo chuẩn bị họp

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| FR-REP-01 | Tóm tắt có cấu trúc | Có bốn phần: bối cảnh, nội dung chính, điểm cần quyết định, tác động |
| FR-REP-02 | Citation cho nhận định quan trọng | Mỗi `SummaryItem` quan trọng có ≥1 ID thuộc citation whitelist |
| FR-REP-03 | Thuật ngữ theo ngữ cảnh | Có ≥10 mục khi tài liệu đủ nội dung; mỗi mục có giải thích và ≥1 citation |
| FR-REP-04 | Câu hỏi phản biện | Có ≥5 câu duy nhất, cụ thể với tài liệu; mỗi câu có rationale và citation |
| FR-REP-05 | Văn bản liên quan | Ưu tiên văn bản được nhắc trực tiếp; nêu nguồn và lý do liên quan |
| FR-REP-06 | Chế độ suy giảm | Khi LLM lỗi/quá hạn, có thể trả fallback grounded và gắn rõ `generation_mode`; không giả là output LLM |
| FR-REP-07 | Kiểm tra chất lượng trước trả kết quả | Không đánh dấu “đạt” nếu thiếu số lượng tối thiểu hoặc citation không hợp lệ |

#### 3.2.3 Citation và xem nguồn

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| FR-CIT-01 | Metadata citation là authoritative | Page/section/article/clause/excerpt lấy từ normalized document, không nhận từ nội dung LLM |
| FR-CIT-02 | Citation whitelist | Mọi ID đầu ra phải tồn tại trong tài liệu hiện tại; ID lạ hoặc không thuộc retrieval set bị loại |
| FR-CIT-03 | Mở nguồn | Từ summary/term/question/Q&A, người dùng mở được trang và excerpt tương ứng |
| FR-CIT-04 | Validation fail-closed | Citation metadata khác chunk hoặc excerpt không khớp source làm output không đạt |

#### 3.2.4 Hỏi đáp

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| FR-QA-01 | Nhận câu hỏi tiếng Việt | Câu hỏi 1–4.000 ký tự, gắn với đúng `document_id` |
| FR-QA-02 | Chỉ dùng evidence trong tài liệu | Retrieval context giới hạn theo tài liệu đang mở |
| FR-QA-03 | Trả lời có citation | Câu trả lời đủ bằng chứng có ≥1 citation hợp lệ và mở được nguồn |
| FR-QA-04 | Từ chối khi thiếu bằng chứng | Trả `insufficient_evidence=true`, câu từ chối chuẩn và `citation_ids=[]` |
| FR-QA-05 | Phân biệt nguồn tham khảo ngoài | Nếu pilot cho phép nguồn ngoài, output phải tách “Trong tài liệu” và “Tham khảo”, có provenance riêng |

#### 3.2.5 Lịch sử và vận hành

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| FR-OPS-01 | Theo dõi lịch sử tác vụ | Lọc được theo user, status, type; có thời gian và lỗi chuẩn hóa |
| FR-OPS-02 | Không đánh đồng history với report | Nếu report không còn sau restart, UI yêu cầu upload lại thay vì mở dữ liệu giả |
| FR-OPS-03 | Quan sát hiệu năng | Ghi latency theo stage, parser/prompt/model version và kết quả quality gate |
| FR-OPS-04 | Xóa dữ liệu | Pilot phải có retention và thao tác xóa tài liệu, derivative, index và audit theo chính sách |

### 3.3 Yêu cầu phi chức năng

| ID | Thuộc tính | Mức hackathon | Mức pilot đề xuất |
|---|---|---|---|
| NFR-PERF-01 | Latency báo cáo | `<60s` trên tài liệu demo công khai ≥40 trang; đo cold run | p95 `<60s` cho lớp 40–60 trang đã định nghĩa |
| NFR-PERF-02 | Q&A latency | Ghi nhận mỗi lượt | p95 ≤3s lexical/extractive; ≤8s nếu có LLM nội bộ |
| NFR-REL-01 | Fail-safe | LLM/enrichment lỗi không tạo citation giả | Tác vụ idempotent, retry có giới hạn, DLQ |
| NFR-REL-02 | Khả năng phục hồi | Chấp nhận mất active report khi restart và phải ghi rõ | Không mất tác vụ đã nhận; RPO/RTO theo hạ tầng đơn vị |
| NFR-SEC-01 | Dữ liệu nội bộ | Không upload khi chưa phê duyệt | On-prem/private network, encryption, RBAC, audit |
| NFR-SEC-02 | Log | Không log body/secret | Redaction, access control, retention |
| NFR-SCALE-01 | Đồng thời | Tối đa theo worker đơn máy, phải benchmark | Capacity plan từ workload pilot, backpressure rõ |
| NFR-UX-01 | Khả năng kiểm chứng | Citation mở trong một thao tác | ≥95% tác vụ usability mở nguồn thành công |
| NFR-ACC-01 | Truy cập | Responsive cơ bản | WCAG 2.1 AA cho luồng chính |
| NFR-COMP-01 | Truy vết | Có task ID và benchmark evidence | Audit bất biến cho truy cập, export, xóa, cấu hình |

Định nghĩa latency bắt đầu khi server nhận đủ bytes và kết thúc khi report bắt buộc sẵn
sàng. Enrichment văn bản liên quan có thể hoàn tất nền sau đó, nhưng UI phải hiển thị
trạng thái và không được tính phần chưa sẵn sàng là “báo cáo hoàn chỉnh” nếu demo yêu
cầu văn bản liên quan trong mốc 60 giây.

### 3.4 Rubric chất lượng

#### Thuật ngữ

Mỗi thuật ngữ chấm 0–2 cho bốn chiều: đúng thuật ngữ xuất hiện, đúng nghĩa theo ngữ
cảnh, ngắn/rõ, citation hỗ trợ trực tiếp. Một mục đạt khi ≥6/8 và không có lỗi citation.
Tối thiểu 10 mục đạt.

#### Câu hỏi phản biện

Mỗi câu chấm 0–1 cho: cụ thể với tài liệu, liên quan quyết định/tác động/rủi ro, không
trùng, có rationale hữu ích, citation hỗ trợ tiền đề. Một câu đạt khi ≥4/5 và citation
hợp lệ. Tối thiểu 5 câu đạt.

#### Q&A

Với câu answerable: faithfulness ≥0,90; answer relevancy, context precision/recall/
relevancy ≥0,80; citation precision ≥0,90 trên golden set. Với câu out-of-scope:
refusal accuracy phải bằng 1,00 trên release set.

### 3.5 KPI và phương pháp đo

| KPI | Công thức | Mục tiêu demo |
|---|---|---:|
| Processing success rate | completed / upload hợp lệ | ≥95% trên tập demo |
| Uncached E2E latency | report_ready_at − upload_received_at | Mọi lần chạy công bố `<60s` |
| Citation validity | citation hợp lệ / citation sinh ra | 100% |
| Citation precision | citation thuộc gold evidence / citation trả về | ≥90% |
| Refusal accuracy | từ chối đúng / câu ngoài phạm vi | 100% |
| Term pass count | thuật ngữ đạt rubric | ≥10/tài liệu chuẩn |
| Question pass count | câu hỏi đạt rubric | ≥5/tài liệu chuẩn |

Mọi KPI phải gắn với dataset version, tài liệu, page count, machine profile, cold/warm,
model, parser version, prompt version và commit SHA. Không suy rộng kết quả từ một tài
liệu luật sang mọi loại tài liệu hành chính.

### 3.6 Hiện trạng và khoảng cách

| Năng lực | Hiện trạng repository | Gap quan trọng |
|---|---|---|
| Upload PDF/DOCX | Có, 25 MB, kiểm tra extension | Chưa kiểm MIME/magic/malware; DOCX chỉ một pseudo-page |
| Xử lý nền | Thread pool 3 worker, active data in-memory | Restart mất report; deadline không hủy công việc đang chạy |
| Tóm tắt | Heuristic fallback; LLM tùy cấu hình cho summary | Health/status chưa phản ánh đúng LLM thực dùng; quality gate chưa chặn |
| Thuật ngữ/câu hỏi | Dictionary/template deterministic | Chất lượng fallback candidate có thể quá chung chung |
| Q&A | Lexical/extractive, fail-closed | Chưa có semantic retrieval; chưa đo đủ đa dạng tài liệu |
| Citation | Whitelist + metadata consistency + excerpt validation | API schema ngoài thiếu `section`/`point`; DOCX thiếu page fidelity |
| Related docs | Regex mention + Tavily nền | Allowlist mặc định có nguồn báo chí; cần ưu tiên nguồn pháp lý chính thức |
| Identity | `X-User-ID` do browser tự tạo | Không phải authentication; truy cập document endpoints chưa owner-scoped |
| Persistence | SQLite chỉ giữ task history | Câu hỏi có thể lưu vào `display_name`; người dùng có thể xóa history theo phiên, nhưng chưa có retention tự động |
| CORS | Wildcard | Không phù hợp pilot/production |

## 4. Strategic Recommendations

### 4.1 Release gates cho demo

Chỉ tuyên bố hoàn thành hackathon khi:

1. Dùng ít nhất một tài liệu công khai thật ≥40 trang và công bố nguồn.
2. Ba cold runs độc lập đều có bằng chứng; lần chạy dùng để demo `<60s`.
3. Bốn phần tóm tắt không rỗng ở những phần áp dụng và mọi item quan trọng có citation.
4. Có ≥10 thuật ngữ và ≥5 câu hỏi đạt human rubric, không chỉ đủ số lượng.
5. Bộ Q&A vàng gồm câu dễ/khó, Điều/Khoản, đa trang và ngoài phạm vi; mọi citation mở
   đúng trang/mục/điều.
6. Demo chế độ từ chối và chế độ provider/enrichment thất bại.
7. Không dùng tài liệu nội bộ hoặc credential thật trong demo công khai.

### 4.2 Ưu tiên sản phẩm

| Thứ tự | Đầu tư | Lý do |
|---:|---|---|
| P0 | Citation fidelity + refusal | Sai nguồn gây rủi ro lớn hơn thiếu tính năng |
| P0 | Quality gate và benchmark tái lập | Ngăn “đủ số lượng nhưng không đủ chất lượng” |
| P0 pilot | Auth/RBAC, private deployment, retention/delete | Điều kiện cần trước dữ liệu nội bộ |
| P1 | DOCX location fidelity và OCR confidence gating | Mở rộng coverage nhưng vẫn bảo toàn provenance |
| P1 | Hybrid retrieval + reranking | Cải thiện recall cho câu hỏi diễn đạt khác nguồn |
| P2 | Kho pháp lý được quản trị | Hữu ích cao nhưng tăng governance và độ phức tạp |

### 4.3 Quyết định cần sponsor phê duyệt trước pilot

1. Phân loại dữ liệu nào được phép xử lý và môi trường triển khai tương ứng.
2. Có cho phép gửi prompt/evidence tới nhà cung cấp AI ngoài đơn vị hay không.
3. Nguồn pháp lý chính thức, tần suất cập nhật và đơn vị chịu trách nhiệm nội dung.
4. Thời hạn lưu tài liệu, report, câu hỏi và audit.
5. Owner nghiệp vụ chịu trách nhiệm nghiệm thu rubric và xử lý phản hồi sai lệch.
