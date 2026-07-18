# Bộ đặc tả Antipaper

## 1. Bối cảnh

Thư mục này là nguồn tham chiếu chính thức cho phạm vi sản phẩm, kiến trúc, hợp đồng
API, kiểm soát an toàn và tiêu chí phát hành của Antipaper. Các tài liệu được viết từ
`problem.txt` và đối chiếu với mã nguồn hiện có tại thời điểm lập đặc tả.

Ba nhãn sau được dùng xuyên suốt:

| Nhãn | Ý nghĩa |
|---|---|
| **MVP hiện tại** | Hành vi đã quan sát được trong repository; vẫn phải qua kiểm thử trước khi tuyên bố phát hành |
| **Mục tiêu hackathon** | Điều kiện phải chứng minh trong demo 48 giờ |
| **Mục tiêu thí điểm/production** | Thiết kế đề xuất cho triển khai có kiểm soát tại UBND; chưa mặc nhiên được triển khai |

## 2. Bản đồ tài liệu

| Tài liệu | Quyết định mà tài liệu quản lý | Đối tượng chính |
|---|---|---|
| [PRD.md](PRD.md) | Vấn đề, phạm vi, yêu cầu, KPI và điều kiện nghiệm thu | Product, nghiệp vụ, ban giám khảo |
| [TECHSTACK.md](TECHSTACK.md) | Công nghệ hiện tại, công nghệ mục tiêu và tiêu chí lựa chọn | Engineering, platform |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Thành phần, ranh giới tin cậy, pipeline và quyết định kiến trúc | Architect, security, engineering |
| [FLOW.md](FLOW.md) | Luồng người dùng, trạng thái tác vụ, citation và nhánh từ chối | Product, frontend, backend, QA |
| [API_CONTRACT.md](API_CONTRACT.md) | Hợp đồng HTTP/JSON v1 và quy tắc tương thích | Frontend, backend, integration |
| [DATA_MODEL.md](DATA_MODEL.md) | Thực thể, quan hệ, vòng đời và lưu giữ dữ liệu | Backend, data, security |
| [SECURITY.md](SECURITY.md) | Threat model, kiểm soát dữ liệu và cổng phê duyệt | Security, platform, lãnh đạo |
| [TEST_STRATEGY.md](TEST_STRATEGY.md) | Kim tự tháp kiểm thử, bộ dữ liệu vàng và release gates | QA, ML/AI, engineering |
| [ROADMAP.md](ROADMAP.md) | Lộ trình 48 giờ, pilot UBND và mở rộng production | Product, delivery, lãnh đạo |
| [ONE_PAGE_DECK.md](ONE_PAGE_DECK.md) | Bản tóm tắt một trang cho trình bày/ra quyết định | Sponsor, ban giám khảo |

## 3. Thứ tự ưu tiên khi có mâu thuẫn

1. Quy định pháp luật, chính sách an toàn thông tin và quyết định của đơn vị triển khai.
2. `PRD.md` đối với phạm vi và tiêu chí nghiệm thu.
3. `API_CONTRACT.md` đối với giao tiếp frontend–backend.
4. `ARCHITECTURE.md`, `DATA_MODEL.md` và `SECURITY.md` đối với thiết kế kỹ thuật.
5. Mã nguồn đang chạy; nếu mã nguồn khác spec thì phải ghi nhận thành gap, không tự ý
   diễn giải spec theo lỗi triển khai.

## 4. Quy tắc thay đổi

- Mọi thay đổi phạm vi phải cập nhật ID yêu cầu trong PRD và các test gate liên quan.
- Thay đổi API phá vỡ tương thích cần phiên bản mới; không tái sử dụng `/api/v1`.
- Thay đổi nhà cung cấp AI hoặc luồng gửi dữ liệu ra ngoài phải qua security review.
- Các con số chất lượng chỉ được tuyên bố khi kèm bộ dữ liệu, phiên bản parser/prompt,
  cấu hình máy, commit SHA và bằng chứng chạy.
- Không đưa khóa bí mật, nội dung tài liệu hoặc dữ liệu cá nhân vào bộ tài liệu này.

