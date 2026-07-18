"""Versioned prompts for grounded Vietnamese meeting intelligence."""

SYSTEM_PROMPT = """Bạn là chuyên gia phân tích tài liệu họp hành chính bằng tiếng Việt.
Chỉ sử dụng bằng chứng nằm trong INPUT. Mỗi nhận định, thuật ngữ và câu hỏi phải
có citation_ids lấy nguyên văn từ chunk_id được cung cấp. Không tự tạo số trang,
Điều, Khoản, căn cứ pháp lý hoặc dữ kiện. Nếu không có bằng chứng trực tiếp, bỏ
qua nội dung đó. Trả đúng JSON schema được client yêu cầu, không thêm văn bản.
"""

MAP_PROMPT = """Phân tích batch {batch_number}/{batch_count}, gồm các trang
{first_page}-{last_page}. Tạo bản nháp có: (1) bối cảnh, (2) nội dung chính,
(3) điểm cần quyết định, (4) tác động; thuật ngữ quan trọng được giải thích theo
ngữ cảnh; và câu hỏi phản biện cụ thể kèm rationale. Không cố đạt số lượng bằng
cách suy đoán. INPUT CHUNKS:\n{chunks_json}
"""

REDUCE_PROMPT = """Hợp nhất các bản nháp batch dưới đây thành một báo cáo không
trùng ý. Giữ đủ bốn phần summary khi có bằng chứng, ưu tiên ít nhất 10 thuật ngữ
và 5 câu hỏi khác nhau nhưng tuyệt đối không thêm nội dung thiếu nguồn. Mọi
citation_ids phải giữ nguyên từ bản nháp. BATCH DRAFTS:\n{drafts_json}
"""
