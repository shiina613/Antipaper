# AI Collaboration Log

## 1. Context

Tài liệu này là chỉ mục bằng chứng về cách nhóm Antipaper sử dụng công cụ AI trong quá trình phân tích, thiết kế, lập trình và kiểm thử. Mục tiêu là giúp ban tổ chức có thể truy vết được: ai sử dụng công cụ nào, vào thời điểm nào, cho hạng mục nào, đầu ra nào được chấp nhận, và con người đã kiểm chứng kết quả ra sao.

> Phạm vi: log cộng tác với AI, không phải application runtime log hoặc LLM observability log.

## 2. Quy tắc bằng chứng

### 2.1 Công cụ AI trực tuyến

- Ghi URL chia sẻ công khai của từng phiên chat.
- Kiểm tra URL trong cửa sổ ẩn danh trước khi nộp.
- Không dùng URL nội bộ chỉ hoạt động với tài khoản của thành viên.

### 2.2 Công cụ AI desktop/IDE

- Export phiên làm việc nếu công cụ hỗ trợ và lưu trong `docs/ai-collaboration/sessions/`.
- Nếu công cụ lưu session cục bộ, ghi đường dẫn gốc chính xác, ví dụ `~/.claude/projects/<project>/` hoặc `~/.codex/sessions/`.
- Chụp ảnh có tên công cụ, prompt chính, phản hồi liên quan và thời gian; lưu trong `docs/ai-collaboration/screenshots/`.
- Mọi bằng chứng phải được tham chiếu từ bảng log bên dưới. Không ghi một session là “đã xác minh” nếu chưa có file, URL hoặc screenshot tương ứng.

### 2.3 Bảo mật và tính toàn vẹn

- Xóa API key, token, mật khẩu, dữ liệu cá nhân và nội dung tài liệu hạn chế trước khi export.
- Không chỉnh sửa ảnh theo cách làm thay đổi nội dung hội thoại; chỉ được che thông tin nhạy cảm và phải ghi chú việc che dữ liệu.
- AI chỉ là công cụ hỗ trợ. Thành viên đứng tên ở cột `Reviewer` chịu trách nhiệm kiểm tra mã nguồn, kết quả test và quyết định cuối cùng.

## 3. Collaboration log

| ID | Thời gian (ICT, UTC+7) | Thành viên | Công cụ | Mục tiêu và prompt tóm tắt | Đầu ra được sử dụng | Kiểm chứng của con người | Bằng chứng | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| AI-001 | 2026-07-18 | Chưa điền | Codex desktop/IDE | Xây dựng AI collaboration log theo yêu cầu trong ảnh của ban tổ chức | Tạo cấu trúc log, quy tắc bằng chứng, mẫu session và liên kết từ README | Cần reviewer kiểm tra nội dung và bổ sung danh tính | Session: cần export; screenshot: cần bổ sung | Chờ bằng chứng |

### Giá trị trạng thái

| Trạng thái | Điều kiện |
|---|---|
| `Chờ bằng chứng` | Có mô tả công việc nhưng thiếu URL, session export hoặc screenshot |
| `Chờ kiểm chứng` | Đã có bằng chứng nhưng chưa ghi reviewer và phương pháp kiểm chứng |
| `Đã xác minh` | Bằng chứng mở được, đầu ra truy vết được và reviewer đã kiểm tra |
| `Không sử dụng` | Đầu ra AI bị loại; phải ghi rõ nguyên nhân để thể hiện quyết định của con người |

## 4. Mẫu entry mới

Sao chép dòng sau vào bảng, không xóa các cột:

```text
| AI-XXX | YYYY-MM-DD HH:mm | Họ tên | Công cụ + phiên bản | Mục tiêu; prompt tóm tắt | File/commit/quyết định tạo ra | Test, review hoặc đối chiếu đã thực hiện | [Session](...) · [Screenshot](...) | Chờ kiểm chứng |
```

Một entry đạt yêu cầu cần trả lời được bốn câu hỏi:

1. AI được yêu cầu làm gì?
2. Phần nào trong phản hồi thực sự đi vào sản phẩm?
3. Con người đã phát hiện, sửa hoặc loại bỏ điều gì?
4. Người đánh giá có thể mở bằng chứng và đối chiếu với repository hay không?

## 5. Checklist trước khi nộp

- [ ] Mỗi công cụ AI đã sử dụng có ít nhất một entry.
- [ ] Mỗi entry có họ tên thành viên và thời gian theo ICT.
- [ ] Link chat trực tuyến mở được khi không đăng nhập.
- [ ] Session desktop/IDE có file export hoặc đường dẫn cục bộ chính xác.
- [ ] Screenshot tương ứng tồn tại trong repository hoặc gói minh chứng nộp kèm.
- [ ] Mỗi đầu ra được sử dụng trỏ tới file hoặc commit cụ thể.
- [ ] Reviewer và phương pháp kiểm chứng đã được ghi.
- [ ] Secret và dữ liệu nhạy cảm đã được loại bỏ.
- [ ] Không còn entry `Chờ bằng chứng` hoặc `Chờ kiểm chứng`.

## 6. Giới hạn hiện tại

Repository tại thời điểm tạo tài liệu chưa chứa chat URL, session export hoặc screenshot lịch sử. Những dữ liệu này không thể tái tạo đáng tin cậy từ mã nguồn; từng thành viên phải export từ công cụ đã dùng và cập nhật log trước khi nộp.
