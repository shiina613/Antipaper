"""Streamlit vertical slice for Antipaper / Paperless Meetings."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from time import perf_counter

import streamlit as st
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from decision import DecisionRadar, DecisionRadarEngine
from ingestion import IngestionOptions, ingest_document
from intelligence import (
    LocalIntelligencePack,
    NormalizedDocument,
    SuggestedQuestion,
    TermExplanation,
    build_local_intelligence_pack,
)
from llm import LlmClient, LlmClientError, LlmSettings
from retrieval import GroundedQAService, RelatedDocumentHit, build_index, extract_related_documents
from summary import DocumentSummary, DocumentSummaryEngine


DEFAULT_YOLO_MODEL_PATH = PROJECT_ROOT / "models" / "table_detect_yolov8.pt"
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
load_dotenv(PROJECT_ROOT / ".env")


def main() -> None:
    st.set_page_config(
        page_title="Antipaper",
        page_icon="📄",
        layout="wide",
    )
    st.title("Antipaper")
    st.caption(
        "Upload PDF/DOCX → tóm tắt có cấu trúc, thuật ngữ, câu hỏi phản biện, "
        "văn bản liên quan và hỏi đáp có citation."
    )

    with st.sidebar:
        st.header("Cấu hình xử lý")
        max_pages = st.number_input(
            "Giới hạn số trang khi test",
            min_value=0,
            max_value=300,
            value=0,
            help="0 nghĩa là xử lý toàn bộ tài liệu.",
        )
        use_yolo = st.checkbox(
            "Bật YOLOv8 table fallback",
            value=False,
            help="Mặc định tắt để ưu tiên fast path PyMuPDF. Bật khi cần detect bảng ảnh.",
        )
        st.divider()
        use_openai_summary = st.checkbox(
            "Dùng OpenAI để tóm tắt",
            value=bool(os.getenv("LLM_API_KEY")),
            help="Nếu chưa có API key hoặc API lỗi, app sẽ fallback về rule-based summary.",
        )
        use_openai_radar = st.checkbox(
            "Dùng OpenAI cho Decision Radar",
            value=False,
            help="Nếu lỗi hoặc chưa có API key, app sẽ fallback về radar rule-based.",
        )
        openai_enabled = use_openai_summary or use_openai_radar
        openai_api_key = st.text_input(
            "OpenAI API key",
            value=os.getenv("LLM_API_KEY", ""),
            type="password",
            disabled=not openai_enabled,
        )
        openai_model = st.text_input(
            "OpenAI model",
            value=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            disabled=not openai_enabled,
        )
        st.caption(
            "Luồng mặc định: PyMuPDF native text + native tables. YOLO/OCR chỉ nên là fallback."
        )

    uploaded_file = st.file_uploader(
        "Chọn PDF hoặc DOCX",
        type=["pdf", "docx"],
        accept_multiple_files=False,
    )
    if uploaded_file is None:
        st.info("Hãy upload tài liệu để bắt đầu.")
        return

    left, mid, right = st.columns(3)
    left.metric("File", uploaded_file.name)
    mid.metric("Dung lượng", f"{uploaded_file.size / (1024 * 1024):.2f} MB")
    right.metric("YOLO fallback", "Bật" if use_yolo else "Tắt")

    if st.button("Phân tích tài liệu", type="primary", use_container_width=True):
        input_path = save_uploaded_file(uploaded_file)
        with st.spinner("Đang chuẩn hóa tài liệu và tạo báo cáo API v1..."):
            started = perf_counter()
            document = ingest_document(
                input_path,
                IngestionOptions(
                    use_yolo_tables=use_yolo,
                    require_yolo_weights=False,
                    yolo_model_path=DEFAULT_YOLO_MODEL_PATH,
                    max_pages=max_pages or None,
                ),
            )
            radar, radar_source, radar_warning = build_radar(
                document=document,
                use_openai=use_openai_radar,
                api_key=openai_api_key,
                model=openai_model,
            )
            summary, summary_source, summary_warning = build_summary(
                document=document,
                use_openai=use_openai_summary,
                api_key=openai_api_key,
                model=openai_model,
            )
            pack = build_local_intelligence_pack(document)
            related_docs = extract_related_documents(document)
            processing_seconds = perf_counter() - started

        st.session_state["normalized_document"] = document
        st.session_state["decision_radar"] = radar
        st.session_state["radar_source"] = radar_source
        st.session_state["radar_warning"] = radar_warning
        st.session_state["document_summary"] = summary
        st.session_state["summary_source"] = summary_source
        st.session_state["summary_warning"] = summary_warning
        st.session_state["intelligence_pack"] = pack
        st.session_state["related_documents"] = related_docs
        st.session_state["processing_seconds"] = processing_seconds
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": (
                    "Tôi đã đọc tài liệu. Hãy hỏi nội dung trong tài liệu; "
                    "tôi chỉ trả lời từ các chunk/citation đã trích xuất."
                ),
                "citation_ids": [],
            }
        ]
        st.success("Phân tích xong.")
        if summary_warning:
            st.warning(summary_warning)
        if radar_warning:
            st.warning(radar_warning)

    document = st.session_state.get("normalized_document")
    radar = st.session_state.get("decision_radar")
    summary = st.session_state.get("document_summary")
    pack = st.session_state.get("intelligence_pack")
    related_docs = st.session_state.get("related_documents")
    if (
        not isinstance(document, NormalizedDocument)
        or not isinstance(radar, DecisionRadar)
        or not isinstance(summary, DocumentSummary)
        or not isinstance(pack, LocalIntelligencePack)
        or not isinstance(related_docs, list)
    ):
        return

    render_result(document, summary, radar, pack, related_docs)


def save_uploaded_file(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> Path:
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(uploaded_file.getbuffer())
        return Path(temp_file.name)


def build_summary(
    *,
    document: NormalizedDocument,
    use_openai: bool,
    api_key: str,
    model: str,
) -> tuple[DocumentSummary, str, str | None]:
    engine = DocumentSummaryEngine()
    if not use_openai:
        return engine.build(document), "rule-based", None

    if not api_key.strip():
        return (
            engine.build(document),
            "rule-based",
            "Chưa có OpenAI API key, đã fallback về tóm tắt rule-based.",
        )

    try:
        api_url = os.getenv("LLM_API_URL", "").strip() or OPENAI_CHAT_COMPLETIONS_URL
        if not api_url.startswith(("http://", "https://")):
            api_url = OPENAI_CHAT_COMPLETIONS_URL

        summary = asyncio.run(
            engine.build_with_llm(
                document,
                llm_client=LlmClient(
                    LlmSettings(
                        api_url=api_url,
                        api_key=api_key.strip(),
                        model=model.strip() or "gpt-4o-mini",
                        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "45")),
                        max_retries=int(os.getenv("LLM_MAX_RETRIES", "1")),
                    )
                ),
            )
        )
        has_content = any(
            (
                summary.executive_summary,
                summary.context,
                summary.main_content,
                summary.decision_points,
                summary.impact,
            )
        )
        if not has_content:
            return (
                engine.build(document),
                "rule-based",
                "OpenAI trả tóm tắt rỗng sau khi lọc citation, đã fallback rule-based.",
            )
        return summary, f"openai:{model.strip() or 'gpt-4o-mini'}", None
    except (LlmClientError, ValueError, RuntimeError) as exc:
        return (
            engine.build(document),
            "rule-based",
            f"OpenAI summary lỗi, đã fallback rule-based: {exc}",
        )


def build_radar(
    *,
    document: NormalizedDocument,
    use_openai: bool,
    api_key: str,
    model: str,
) -> tuple[DecisionRadar, str, str | None]:
    engine = DecisionRadarEngine()
    if not use_openai:
        return engine.build(document), "rule-based", None

    if not api_key.strip():
        return (
            engine.build(document),
            "rule-based",
            "Chưa có OpenAI API key, đã fallback Decision Radar về rule-based.",
        )

    try:
        api_url = os.getenv("LLM_API_URL", "").strip() or OPENAI_CHAT_COMPLETIONS_URL
        if not api_url.startswith(("http://", "https://")):
            api_url = OPENAI_CHAT_COMPLETIONS_URL

        radar = asyncio.run(
            engine.build_with_llm(
                document,
                llm_client=LlmClient(
                    LlmSettings(
                        api_url=api_url,
                        api_key=api_key.strip(),
                        model=model.strip() or "gpt-4o-mini",
                        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "45")),
                        max_retries=int(os.getenv("LLM_MAX_RETRIES", "1")),
                    )
                ),
            )
        )
        return radar, f"openai:{model.strip() or 'gpt-4o-mini'}", None
    except (LlmClientError, ValueError, RuntimeError) as exc:
        return (
            engine.build(document),
            "rule-based",
            f"OpenAI Decision Radar lỗi, đã fallback rule-based: {exc}",
        )


def render_result(
    document: NormalizedDocument,
    summary: DocumentSummary,
    radar: DecisionRadar,
    pack: LocalIntelligencePack,
    related_docs: list[RelatedDocumentHit],
) -> None:
    st.divider()
    processing_seconds = float(st.session_state.get("processing_seconds", 0.0))
    cols = st.columns(6)
    cols[0].metric("Số trang", document.page_count)
    cols[1].metric("Thời gian xử lý", f"{processing_seconds:.2f}s")
    cols[2].metric("Chunks", len(document.chunks))
    cols[3].metric("Thuật ngữ", len(pack.terms))
    cols[4].metric("Câu hỏi", len(pack.suggested_questions))
    cols[5].metric("Văn bản liên quan", len(related_docs))

    sections = [
        "Tóm tắt",
        "Thuật ngữ",
        "Câu hỏi phản biện",
        "Văn bản liên quan",
        "Decision Radar",
        "Hỏi đáp",
        "Chunks & citations",
        "Xuất JSON",
    ]
    active = st.radio(
        "Chọn nội dung",
        sections,
        horizontal=True,
        key="active_report_section",
        label_visibility="collapsed",
    )

    if active == "Tóm tắt":
        render_summary(summary)
    elif active == "Thuật ngữ":
        render_terms(pack.terms, document)
    elif active == "Câu hỏi phản biện":
        render_questions(pack.suggested_questions, document)
    elif active == "Văn bản liên quan":
        render_related_documents(related_docs, document)
    elif active == "Decision Radar":
        render_radar(radar)
    elif active == "Hỏi đáp":
        render_chatbot(document)
    elif active == "Chunks & citations":
        render_chunks(document)
    elif active == "Xuất JSON":
        render_download(document, summary, radar, pack, related_docs, processing_seconds)


def render_summary(summary: DocumentSummary) -> None:
    st.subheader("Tóm tắt có cấu trúc")
    summary_source = st.session_state.get("summary_source", "unknown")
    st.caption(f"Nguồn tóm tắt: `{summary_source}`.")
    summary_warning = st.session_state.get("summary_warning")
    if summary_warning:
        st.warning(summary_warning)

    has_structured = any(
        (summary.context, summary.main_content, summary.decision_points, summary.impact)
    )
    if not has_structured and not summary.executive_summary:
        st.error(
            "Tóm tắt đang trống. Thường do mô hình trả citation_id không khớp chunk. "
            "Hãy phân tích lại (đã có fallback rule-based ở bản mới)."
        )

    if summary.executive_summary:
        st.markdown("#### Tóm tắt điều hành")
        for item in summary.executive_summary:
            st.write(item.text)
            if item.citation_ids:
                st.caption("Citations: " + ", ".join(item.citation_ids))

    sections = [
        ("Bối cảnh", summary.context),
        ("Nội dung chính", summary.main_content),
        ("Điểm cần quyết định", summary.decision_points),
        ("Tác động", summary.impact),
    ]
    for title, items in sections:
        st.markdown(f"#### {title}")
        if not items:
            st.caption("Chưa có nội dung.")
            continue
        for item in items:
            st.write(item.text)
            if item.citation_ids:
                st.caption("Citations: " + ", ".join(item.citation_ids))


def render_terms(terms: list[TermExplanation], document: NormalizedDocument) -> None:
    st.subheader("Thuật ngữ / điều khoản quan trọng")
    st.caption("Mỗi thuật ngữ có giải thích theo ngữ cảnh và citation nguồn trong tài liệu.")
    if len(terms) < 10:
        st.warning(f"Chỉ phát hiện {len(terms)} thuật ngữ (yêu cầu ≥10).")
    for term in terms:
        with st.expander(term.term, expanded=False):
            st.write(term.explanation)
            st.caption("Citations: " + ", ".join(term.citation_ids))
            for citation_id in term.citation_ids:
                locator = format_citation_locator(document, citation_id)
                if locator:
                    st.caption(locator)


def render_questions(questions: list[SuggestedQuestion], document: NormalizedDocument) -> None:
    st.subheader("Câu hỏi phản biện")
    st.caption("Câu hỏi gắn với chính tài liệu; mỗi câu có rationale và citation.")
    if len(questions) < 5:
        st.warning(f"Chỉ có {len(questions)} câu hỏi (yêu cầu ≥5).")
    for index, question in enumerate(questions, start=1):
        st.markdown(f"**{index}. {question.question}**")
        st.write(question.rationale)
        st.caption("Citations: " + ", ".join(question.citation_ids))
        for citation_id in question.citation_ids:
            locator = format_citation_locator(document, citation_id)
            if locator:
                st.caption(locator)
        st.divider()


def render_related_documents(
    related_docs: list[RelatedDocumentHit],
    document: NormalizedDocument,
) -> None:
    st.subheader("Văn bản / quy định liên quan")
    st.caption(
        "Ưu tiên căn cứ được nhắc trong tài liệu, đối chiếu catalog cục bộ "
        "(`docs/fixtures/related_documents_catalog.json`). Không bịa văn bản."
    )
    if not related_docs:
        st.info("Không phát hiện văn bản liên quan có số hiệu/tên rõ trong tài liệu.")
        return
    for item in related_docs:
        title = f"{item.title} ({item.document_number})"
        with st.expander(title, expanded=False):
            st.write(item.reason)
            st.caption(f"Nguồn: `{item.source}` | Catalog: {'có' if item.catalog_matched else 'không'}")
            if item.url:
                st.caption(f"URL: {item.url}")
            st.caption("Citations: " + ", ".join(item.citation_ids))
            for citation_id in item.citation_ids[:3]:
                locator = format_citation_locator(document, citation_id)
                if locator:
                    st.caption(locator)


def render_radar(radar: DecisionRadar) -> None:
    st.subheader("Decision & Risk Radar")
    radar_source = st.session_state.get("radar_source", "unknown")
    st.caption(f"Nguồn radar: `{radar_source}`. Mỗi finding giữ citation_id về chunk nguồn.")
    radar_warning = st.session_state.get("radar_warning")
    if radar_warning:
        st.warning(radar_warning)
    sections = [
        ("Vấn đề cần quyết định", radar.decision_points),
        ("Căn cứ pháp lý", radar.legal_basis),
        ("Trách nhiệm", radar.responsibilities),
        ("Thời hạn", radar.deadlines),
        ("Nguồn lực", radar.resources),
        ("Rủi ro", radar.risks),
        ("Điểm còn bỏ ngỏ", radar.open_questions),
    ]
    for title, items in sections:
        with st.expander(f"{title} ({len(items)})", expanded=bool(items)):
            if not items:
                st.caption("Chưa phát hiện tín hiệu rõ ràng.")
                continue
            for item in items:
                st.markdown(f"**{item.finding}**")
                st.caption(
                    f"Confidence: {item.confidence:.2f} | Citations: {', '.join(item.citation_ids)}"
                )
                st.divider()


def render_chatbot(document: NormalizedDocument) -> None:
    st.subheader("Chatbot hỏi đáp theo tài liệu")
    st.caption(
        "Chatbot chỉ dùng `NormalizedDocument.chunks`. Nếu không đủ bằng chứng, nó sẽ từ chối."
    )
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    for message in st.session_state["chat_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            citations = message.get("citation_ids") or []
            if citations:
                st.caption("Citations: " + ", ".join(citations))
                for citation_id in citations:
                    locator = format_citation_locator(document, citation_id)
                    if locator:
                        st.caption(locator)

    prompt = st.chat_input("Hỏi nội dung trong tài liệu này...")
    if not prompt:
        return

    st.session_state["chat_messages"].append(
        {"role": "user", "content": prompt, "citation_ids": []}
    )
    answer = asyncio.run(GroundedQAService(build_index(document)).answer(prompt))
    st.session_state["chat_messages"].append(
        {
            "role": "assistant",
            "content": answer.answer,
            "citation_ids": answer.citation_ids,
        }
    )
    st.rerun()


def render_chunks(document: NormalizedDocument) -> None:
    st.subheader("Chunks & citations")
    st.caption("Mỗi chunk là một đơn vị bằng chứng mà chatbot/LLM được phép cite.")
    for chunk in document.chunks:
        locator = " / ".join(
            part
            for part in [
                f"Trang {chunk.page}",
                chunk.chapter,
                chunk.section,
                chunk.article,
                chunk.clause,
                chunk.point,
            ]
            if part
        )
        with st.expander(f"{chunk.chunk_id} - {locator}", expanded=False):
            st.write(chunk.text)
            citation = document.citations.get(chunk.chunk_id)
            if citation:
                st.caption(f"Excerpt: {citation.excerpt}")


def render_download(
    document: NormalizedDocument,
    summary: DocumentSummary,
    radar: DecisionRadar,
    pack: LocalIntelligencePack,
    related_docs: list[RelatedDocumentHit],
    processing_seconds: float,
) -> None:
    payload = {
        "document_id": document.document_id,
        "file_name": document.file_name,
        "page_count": document.page_count,
        "processing_seconds": processing_seconds,
        "summary": {
            "context": [item.model_dump(mode="json") for item in summary.context],
            "main_content": [item.model_dump(mode="json") for item in summary.main_content],
            "decision_points": [item.model_dump(mode="json") for item in summary.decision_points],
            "impact": [item.model_dump(mode="json") for item in summary.impact],
        },
        "terms": [term.model_dump(mode="json") for term in pack.terms],
        "suggested_questions": [
            question.model_dump(mode="json") for question in pack.suggested_questions
        ],
        "related_documents": [
            {
                "title": item.title,
                "document_number": item.document_number,
                "source": item.source,
                "reason": item.reason,
                "citation_ids": item.citation_ids,
                "url": item.url,
            }
            for item in related_docs
        ],
        "citations": {
            chunk_id: citation.model_dump(mode="json")
            for chunk_id, citation in document.citations.items()
        },
        "decision_radar": radar.model_dump(mode="json"),
        "document": document.model_dump(mode="json"),
    }
    st.download_button(
        label="Tải báo cáo JSON (API v1)",
        data=json.dumps(payload, ensure_ascii=False, indent=2),
        file_name="antipaper_report_v1.json",
        mime="application/json",
        use_container_width=True,
    )


def format_citation_locator(document: NormalizedDocument, citation_id: str) -> str | None:
    citation = document.citations.get(citation_id)
    chunk = next((item for item in document.chunks if item.chunk_id == citation_id), None)
    page = citation.page if citation else (chunk.page if chunk else None)
    if page is None:
        return None
    parts = [f"Trang {page}"]
    for value in (
        (citation.chapter if citation else None) or (chunk.chapter if chunk else None),
        (citation.section if citation else None) or (chunk.section if chunk else None),
        (citation.article if citation else None) or (chunk.article if chunk else None),
        (citation.clause if citation else None) or (chunk.clause if chunk else None),
        (citation.point if citation else None) or (chunk.point if chunk else None),
    ):
        if value:
            parts.append(value)
    return " · ".join(parts)


if __name__ == "__main__":
    main()
