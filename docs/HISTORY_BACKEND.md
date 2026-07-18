# Backend lịch sử lượt tác vụ

## Context

Antipaper dùng SHA-256 làm `document_id` để tái sử dụng artifact đã xử lý. Cơ chế
này tối ưu chi phí nhưng không thể đại diện cho lịch sử sử dụng: hai người dùng
upload cùng một tệp, hoặc một người upload lại ở hai thời điểm, vẫn trỏ đến cùng
một tài liệu.

## Problem Statement

Hệ thống cần lưu từng lần người dùng chủ động gọi một tác vụ, theo dõi được trạng
thái và thời điểm, đồng thời không phá vỡ cache tài liệu hoặc hợp đồng API hiện
tại. Dữ liệu lịch sử phải tồn tại sau khi backend khởi động lại và không được trả
chéo giữa các định danh người dùng.

## Technical Deep-Dive

Mô hình tách hai thực thể:

| Thực thể | Định danh | Trách nhiệm |
|---|---|---|
| Document | SHA-256 `document_id` | Artifact, report, page và retrieval index có thể dùng lại |
| Task run | UUID `task_id` | Một lần upload hoặc hỏi đáp của một người dùng tại một thời điểm |

SQLite được đặt tại `${ARTIFACT_DIR}/history.sqlite3`, bật WAL và `busy_timeout`.
Các index `(user_id, created_at)`, `(user_id, status)` và
`(document_id, task_type, status)` giữ độ trễ truy vấn ổn định cho workload demo
đơn node. Worker xử lý tài liệu phát sự kiện khi chuyển trạng thái; history cập
nhật mọi task document chưa kết thúc và không cho phép trạng thái terminal bị
hạ cấp bởi một sự kiện đến muộn.

| Iron Triangle | Đánh giá hiện tại | Ngưỡng cần nâng cấp |
|---|---|---|
| Scalability | Phù hợp một process hoặc một node với lưu lượng MVP | Nhiều replica ghi đồng thời hoặc hàng triệu task cần PostgreSQL và cursor pagination |
| Reliability | Giao dịch SQLite, WAL, dữ liệu tồn tại qua restart, trạng thái terminal đơn điệu | Cần outbox/event queue nếu worker được tách sang tiến trình hoặc máy khác |
| Latency | Truy vấn index cục bộ, không thêm network hop | Cần partition/index chuyên biệt khi lọc lịch sử dài hạn ở quy mô lớn |

`X-User-ID` hiện là ranh giới phân vùng cho demo, không phải chứng cứ xác thực.
Khi triển khai production, middleware xác thực phải ghi đè giá trị này bằng
`sub`/user claim từ token; không được tin header do client tự khai báo.

## Strategic Recommendations

1. Frontend giữ `task_id` trả về sau upload/question và polling history detail khi
   cần hiển thị tiến độ theo từng lượt.
2. Mount `ARTIFACT_DIR` trên persistent volume; nếu dùng filesystem tạm thời thì
   history và cache đều mất sau redeploy.
3. Khi chuyển sang nhiều replica, thay `TaskHistoryStore` bằng repository
   PostgreSQL nhưng giữ nguyên schema Pydantic và API để giảm chi phí tích hợp.
4. Không lưu toàn văn tài liệu trong history. `display_name` chỉ chứa tên tệp hoặc
   tối đa 160 ký tự câu hỏi nhằm giới hạn dữ liệu nhạy cảm và kích thước bản ghi.
