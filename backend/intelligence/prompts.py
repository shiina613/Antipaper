"""Versioned prompts for grounded Vietnamese meeting intelligence."""

SYSTEM_PROMPT = """Bạn là chuyên gia phân tích và biên tập tài liệu hành chính bằng tiếng Việt.
Chỉ sử dụng bằng chứng nằm trong INPUT. Mỗi nhận định, thuật ngữ và câu hỏi phải
có citation_ids lấy nguyên văn từ chunk_id được cung cấp. Không tự tạo số trang,
Điều, Khoản, căn cứ pháp lý hoặc dữ kiện. Phải diễn giải và tổng hợp thành văn bản
mạch lạc; không sao chép hoặc nối cơ học các câu rời rạc từ nguồn. Nếu không có
bằng chứng trực tiếp, bỏ qua nội dung đó. Trả đúng JSON schema được client yêu cầu,
không thêm văn bản ngoài JSON.
"""

MAP_PROMPT = """Phân tích batch {batch_number}/{batch_count}, gồm các trang
{first_page}-{last_page}. Tạo bản nháp có: (1) bối cảnh, (2) nội dung chính,
(3) điểm cần quyết định, (4) tác động; và 5-20 thuật ngữ, điều khoản, tên chương
trình, chỉ số hoặc khái niệm chuyên môn quan trọng của batch được giải thích ngắn
theo đúng ngữ cảnh. Mỗi term dùng một citation_id trực tiếp và không được trả mảng
terms rỗng nếu batch có nội dung có nghĩa. Để suggested_questions là mảng rỗng vì câu hỏi sẽ được tạo sau khi đã có
bản tóm tắt toàn tài liệu. Với mỗi nhóm summary, tạo các EvidenceItem riêng cho
từng chủ đề hoặc luận điểm khác nhau. Phải rà soát toàn bộ INPUT CHUNKS và bao phủ
mọi nội dung có ý nghĩa trong batch, gồm mục tiêu/phạm vi, luận điểm, số liệu,
phương án, chủ thể/trách nhiệm, mốc thời gian, điều kiện, ngoại lệ, quyết định và
tác động/rủi ro nếu nguồn có đề cập. Mỗi EvidenceItem phải là một ý tổng hợp độc
lập, không trùng ý và sẽ được hiển thị thành một gạch đầu dòng; không chèn ký hiệu
gạch đầu dòng vào text. Gắn tất cả citation_ids thực sự được dùng cho từng ý.
Không cố đạt số lượng bằng cách suy đoán. INPUT CHUNKS:\n{chunks_json}
"""

REDUCE_PROMPT = """Biên tập các bản nháp batch dưới đây thành một báo cáo thống
nhất, không trùng ý. Riêng summary phải tuân thủ chính xác các yêu cầu sau:
- Tổng nội dung text của cả bốn mảng context, main_content, decision_points và
  impact không vượt quá 800 từ tiếng Việt; hướng tới 500-800 từ khi tài liệu có đủ
  nội dung. Giới hạn 800 từ áp dụng cho toàn bộ summary, không phải cho từng mảng.
- Mỗi EvidenceItem là một gạch đầu dòng độc lập khoảng 25-90 từ, trình bày một chủ
  đề hoặc luận điểm hoàn chỉnh. Trả nhiều EvidenceItem khi có nhiều ý; không chèn
  ký hiệu "-", "•" hoặc số thứ tự vào text vì giao diện tự định dạng danh sách.
- Trước khi trả kết quả, đối chiếu lần lượt tất cả batch để bảo đảm mọi chương/phần
  và mọi chủ đề có ý nghĩa đều được đại diện ít nhất một lần. Không được bỏ sót
  mục tiêu, phạm vi, luận điểm, số liệu quan trọng, phương án, chủ thể và trách
  nhiệm, mốc thời gian, điều kiện/ngoại lệ, nội dung cần quyết định, tác động hoặc
  rủi ro đã xuất hiện trong nguồn; gộp các chi tiết liên quan để tránh trùng lặp.
- context giải thích mục đích, phạm vi và hoàn cảnh của tài liệu; main_content tổng
  hợp luận điểm, phương án và dữ kiện cốt lõi; decision_points chỉ nêu vấn đề thực
  sự cần lựa chọn, phê duyệt, kết luận hoặc giao trách nhiệm; impact phân tích hệ quả,
  đối tượng chịu ảnh hưởng, nguồn lực, tiến độ hoặc rủi ro có bằng chứng.
- Mỗi EvidenceItem dùng 1-6 citation_ids trực tiếp hỗ trợ riêng cho ý đó;
  citation_ids phải giữ nguyên từ bản nháp, không tự tạo ID. Phân bổ nguồn trên
  toàn tài liệu thay vì chỉ trích các trang đầu hoặc lặp cùng một nhóm nguồn.
Tiếp tục hợp nhất 10-100 thuật ngữ/điều khoản quan trọng nhất từ các batch, mỗi
thuật ngữ chỉ dùng một nguồn tiêu biểu. Không gộp các khái niệm khác nghĩa và không
giữ các biến thể trùng lặp. Để suggested_questions là mảng rỗng vì câu hỏi sẽ được sinh ở bước kế
tiếp từ bản tóm tắt đã hợp nhất. Tuyệt đối không thêm nội dung thiếu nguồn.
BATCH DRAFTS:\n{drafts_json}
"""

TERM_PROMPT = """Dựa trên FINAL SUMMARY, BATCH TERM CANDIDATES và EVIDENCE CHUNKS
của chính tài liệu này, lập danh sách thuật ngữ/điều khoản cần làm rõ.

Yêu cầu bắt buộc:
- Trả ít nhất 10 và không quá 100 mục; ưu tiên 10-30 mục quan trọng nhất đối với
  việc hiểu tài liệu và ra quyết định. Không trả mảng terms rỗng khi nguồn có nội dung.
- Có thể chọn thuật ngữ pháp lý, Điều/Khoản, cơ quan/chủ thể, chương trình/đề án,
  quy trình, chỉ số, chữ viết tắt, tiêu chí, nguồn lực hoặc khái niệm kỹ thuật.
- term phải là tên/cụm từ ngắn xuất hiện trực tiếp trong evidence, không phải cả câu.
- explanation gồm 1-2 câu ngắn, giải thích term có nghĩa hoặc vai trò gì trong đúng
  ngữ cảnh tài liệu; không dùng định nghĩa chung từ kiến thức bên ngoài.
- Mỗi mục dùng đúng một citation_id trực tiếp từ EVIDENCE CHUNKS. Không tự tạo ID.
- Không lặp từ, biến thể viết hoa/viết thường, số ít/số nhiều hoặc các cụm đồng nghĩa.
- Trả IntelligenceDraft với summary gồm bốn mảng rỗng, suggested_questions là mảng
  rỗng và terms chứa danh sách kết quả. Không thêm văn bản ngoài JSON.

FINAL SUMMARY:\n{summary_json}

BATCH TERM CANDIDATES:\n{candidates_json}

EVIDENCE CHUNKS:\n{chunks_json}
"""

QUESTION_PROMPT = """Dựa trên FINAL SUMMARY đã hợp nhất và EVIDENCE CHUNKS của
chính tài liệu này, tạo đúng 5 câu hỏi phản biện bằng tiếng Việt cho cuộc họp.

Yêu cầu bắt buộc:
- Mỗi câu hỏi phải nhắc trực tiếp ít nhất một chủ thể, số liệu, phương án, thời hạn,
  kết luận hoặc vấn đề cụ thể xuất hiện trong FINAL SUMMARY; không viết câu hỏi chung
  có thể tái sử dụng nguyên văn cho một tài liệu khác.
- Câu hỏi phải kiểm tra một giả định, khoảng trống dữ liệu, tiêu chí lựa chọn, đánh
  đổi, rủi ro, trách nhiệm hoặc điều kiện triển khai chưa được làm rõ; không chỉ hỏi
  người đọc nhắc lại nội dung tóm tắt.
- Năm câu hỏi phải khác nhau về vấn đề được phản biện và bám sát nội dung tài liệu.
- rationale giải thích ngắn gọn câu trả lời sẽ hỗ trợ quyết định nào trong cuộc họp.
- citation_ids chỉ được lấy nguyên văn từ chunk_id trong EVIDENCE CHUNKS và phải trực
  tiếp hỗ trợ tiền đề được nêu trong câu hỏi. Với từng câu hỏi, liệt kê đầy đủ, không
  trùng lặp tất cả chunk_id đã dùng để hình thành các tiền đề cụ thể; không cố định
  một citation, không dùng chung máy móc citation_ids giữa năm câu hỏi và không đưa
  vào nguồn không được dùng. Không tự tạo dữ liệu hoặc citation ID.
- Trả IntelligenceDraft với summary gồm bốn mảng rỗng, terms là mảng rỗng và
  suggested_questions chứa đúng 5 phần tử. Không thêm văn bản ngoài JSON.

FINAL SUMMARY:\n{summary_json}

EVIDENCE CHUNKS:\n{chunks_json}
"""
