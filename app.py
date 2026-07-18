"""Streamlit app that runs the full Paperless Meetings MVP pipeline."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from intelligence import MeetingIntelligenceEngine, MeetingIntelligenceReport
from pipeline.processor import PdfProcessingPipeline, ProcessedDocument


DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "table_detect_yolov8.pt"
DEFAULT_QUESTION = "Tài liệu này yêu cầu người dự họp cần lưu ý những nội dung chính nào?"


def main() -> None:
    st.set_page_config(
        page_title="Paperless Meetings",
        page_icon="📄",
        layout="wide",
    )

    st.title("Paperless Meetings")
    st.caption(
        "Upload PDF -> trích xuất nội dung -> tóm tắt -> thuật ngữ -> câu hỏi gợi ý -> Q&A có trích dẫn trang."
    )

    render_sidebar()

    if not DEFAULT_MODEL_PATH.exists():
        st.error(
            "Chưa tìm thấy YOLO weights tại "
            f"`{DEFAULT_MODEL_PATH}`. Hãy chạy `python download_yolo_table_weights.py` trước."
        )
        st.stop()

    uploaded_file = st.file_uploader(
        "Chọn file PDF cần phân tích",
        type=["pdf"],
        accept_multiple_files=False,
    )

    if uploaded_file is None:
        st.info("Hãy upload một file PDF để bắt đầu.")
        return

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("File", uploaded_file.name)
    with col_b:
        st.metric("Dung lượng", f"{uploaded_file.size / (1024 * 1024):.2f} MB")
    with col_c:
        st.metric("Model", DEFAULT_MODEL_PATH.name)

    with st.sidebar:
        max_pages = st.number_input(
            "Giới hạn số trang khi test",
            min_value=0,
            max_value=300,
            value=0,
            help="Đặt 0 để xử lý toàn bộ tài liệu.",
        )
        confidence = st.slider("YOLO confidence", 0.05, 0.95, 0.25, 0.05)
        render_scale = st.slider("Render scale", 1.0, 3.0, 2.0, 0.25)

    if st.button("Phân tích tài liệu", type="primary", use_container_width=True):
        pdf_path = save_uploaded_pdf(uploaded_file)
        with st.spinner("Đang xử lý PDF, phát hiện bảng và tạo báo cáo..."):
            document = get_pipeline(
                model_path=str(DEFAULT_MODEL_PATH),
                confidence_threshold=confidence,
                render_scale=render_scale,
            ).process(
                pdf_path,
                max_pages=max_pages or None,
            )
            report = get_engine().build_report(
                document=document,
                sample_question=DEFAULT_QUESTION,
            )

        st.session_state["document"] = document
        st.session_state["report"] = report
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": (
                    "Tôi đã đọc PDF này. Bạn có thể hỏi về nội dung trong tài liệu; "
                    "tôi chỉ trả lời dựa trên PDF vừa upload."
                ),
                "citations": [],
            }
        ]
        st.success("Phân tích xong.")

    document = st.session_state.get("document")
    report = st.session_state.get("report")
    if document is None or report is None:
        return

    render_report(document=document, report=report)


def render_sidebar() -> None:
    with st.sidebar:
        st.header("Cấu hình")
        st.markdown(
            """
            **Luồng xử lý**

            1. Render PDF bằng PyMuPDF  
            2. YOLOv8 detect bảng  
            3. Mask vùng bảng khi lấy native text  
            4. Stitch text + markdown table  
            5. Sinh summary, thuật ngữ, câu hỏi và Q&A
            """
        )
        st.divider()
        st.caption("MVP hiện dùng rule-based intelligence và table markdown placeholder.")


@st.cache_resource(show_spinner=False)
def get_pipeline(
    model_path: str,
    confidence_threshold: float,
    render_scale: float,
) -> PdfProcessingPipeline:
    return PdfProcessingPipeline(
        model_path=model_path,
        confidence_threshold=confidence_threshold,
        render_scale=render_scale,
    )


@st.cache_resource(show_spinner=False)
def get_engine() -> MeetingIntelligenceEngine:
    return MeetingIntelligenceEngine()


def save_uploaded_pdf(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> Path:
    suffix = Path(uploaded_file.name).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(uploaded_file.getbuffer())
        return Path(temp_file.name)


def render_report(
    document: ProcessedDocument,
    report: MeetingIntelligenceReport,
) -> None:
    st.divider()
    st.subheader("Kết quả xử lý")

    metric_cols = st.columns(4)
    metric_cols[0].metric("Số trang", document.page_count)
    metric_cols[1].metric("Thời gian xử lý", f"{document.processing_seconds:.2f}s")
    metric_cols[2].metric("Bảng phát hiện", count_tables(document))
    metric_cols[3].metric("Ký tự trích xuất", len(document.full_text))

    tabs = st.tabs(
        [
            "Tóm tắt",
            "Thuật ngữ",
            "Câu hỏi gợi ý",
            "Hỏi đáp",
            "Nội dung theo trang",
            "Xuất báo cáo",
        ]
    )

    with tabs[0]:
        render_summary(report)

    with tabs[1]:
        render_terms(report)

    with tabs[2]:
        render_questions(report)

    with tabs[3]:
        render_qa(document)

    with tabs[4]:
        render_pages(document)

    with tabs[5]:
        render_download(report)


def render_summary(report: MeetingIntelligenceReport) -> None:
    summary = report.summary
    col_1, col_2 = st.columns(2)

    with col_1:
        render_bullet_section("Bối cảnh", summary.context)
        render_bullet_section("Nội dung chính", summary.main_content)
        render_bullet_section("Điểm cần quyết định", summary.decision_points)

    with col_2:
        render_bullet_section("Tác động", summary.impact)
        render_bullet_section("Rủi ro / lưu ý", summary.risks)


def render_terms(report: MeetingIntelligenceReport) -> None:
    st.caption("Danh sách thuật ngữ chuyên ngành được phát hiện trong tài liệu.")
    for index, term in enumerate(report.terms[:20], start=1):
        pages = ", ".join(f"Trang {page}" for page in term.pages) or "Không rõ trang"
        with st.expander(f"{index}. {term.term} - {pages}", expanded=index <= 10):
            st.write(term.explanation)
            st.caption(f"Bằng chứng: {term.evidence}")


def render_questions(report: MeetingIntelligenceReport) -> None:
    for index, question in enumerate(report.questions, start=1):
        st.markdown(f"**{index}. {question.question}**")
        st.write(question.rationale)
        if question.citations:
            st.caption("Gợi ý tra cứu: " + ", ".join(question.citations))
        st.divider()


def render_qa(document: ProcessedDocument) -> None:
    st.caption(
        "Chatbot chỉ dùng PDF đã upload trong phiên hiện tại. Nếu không tìm thấy bằng chứng, bot sẽ từ chối trả lời."
    )

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": "Tôi đã sẵn sàng trả lời dựa trên PDF đã upload.",
                "citations": [],
            }
        ]

    for message in st.session_state["chat_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            citations = message.get("citations") or []
            if citations:
                st.caption("Trích dẫn: " + ", ".join(citations))

    prompt = st.chat_input("Hỏi nội dung trong PDF này...")
    if not prompt:
        return

    st.session_state["chat_messages"].append(
        {"role": "user", "content": prompt, "citations": []}
    )

    answer = get_engine().answer_question_from_document(
        document=document,
        question=prompt,
    )
    st.session_state["chat_messages"].append(
        {
            "role": "assistant",
            "content": answer.answer,
            "citations": answer.citations,
        }
    )
    st.rerun()


def render_pages(document: ProcessedDocument) -> None:
    for page in document.stitched_pages:
        with st.expander(f"Trang {page.page_number}", expanded=page.page_number == 1):
            st.text_area(
                label=f"Nội dung trang {page.page_number}",
                value=page.content,
                height=280,
                label_visibility="collapsed",
            )


def render_download(report: MeetingIntelligenceReport) -> None:
    report_json = json.dumps(asdict(report), ensure_ascii=False, indent=2)
    st.download_button(
        label="Tải báo cáo JSON",
        data=report_json,
        file_name="paperless_meetings_report.json",
        mime="application/json",
        use_container_width=True,
    )


def render_bullet_section(title: str, items: list[str]) -> None:
    st.markdown(f"### {title}")
    if not items:
        st.caption("Chưa có nội dung.")
        return
    for item in items:
        st.markdown(f"- {item}")


def count_tables(document: ProcessedDocument) -> int:
    return sum(len(tables) for tables in document.tables_by_page.values())


if __name__ == "__main__":
    main()
