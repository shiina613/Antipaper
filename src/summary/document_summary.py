"""Rule-based structured summary over NormalizedDocument chunks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.intelligence.contracts import DocumentChunk, NormalizedDocument
from src.llm import LlmClient


class SummaryItem(BaseModel):
    """One summary statement with direct citations."""

    model_config = ConfigDict(extra="forbid")

    text: str
    citation_ids: list[str] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    """Structured summary sections for the dashboard."""

    model_config = ConfigDict(extra="forbid")

    executive_summary: list[SummaryItem] = Field(default_factory=list)
    context: list[SummaryItem] = Field(default_factory=list)
    main_content: list[SummaryItem] = Field(default_factory=list)
    decision_points: list[SummaryItem] = Field(default_factory=list)
    impact: list[SummaryItem] = Field(default_factory=list)
    risks: list[SummaryItem] = Field(default_factory=list)


class DocumentSummaryEngine:
    """Fast local summary for the vertical slice before LLM integration."""

    _rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("executive_summary", ("luật", "quy định", "trách nhiệm", "quyền", "nghĩa vụ", "thực hiện")),
        ("context", ("luật", "nghị quyết", "quyết định", "căn cứ", "phạm vi", "mục tiêu")),
        ("main_content", ("quy định", "nội dung", "nghĩa vụ", "quyền", "điều kiện", "thực hiện")),
        ("decision_points", ("quyết định", "phê duyệt", "thống nhất", "thông qua", "yêu cầu")),
        ("impact", ("tác động", "trách nhiệm", "người dân", "cơ quan", "tổ chức", "gia đình")),
        ("risks", ("rủi ro", "cấm", "không được", "trái pháp luật", "xử lý", "thiếu")),
    )

    def build(self, document: NormalizedDocument, limit_per_section: int = 4) -> DocumentSummary:
        buckets: dict[str, list[SummaryItem]] = {field: [] for field, _ in self._rules}
        for field_name, keywords in self._rules:
            for chunk in self._rank_chunks(document.chunks, keywords):
                if len(buckets[field_name]) >= limit_per_section:
                    break
                buckets[field_name].append(
                    SummaryItem(
                        text=self._shorten(chunk.text),
                        citation_ids=[chunk.chunk_id],
                    )
                )

        if not buckets["context"] and document.chunks:
            first_chunk = document.chunks[0]
            buckets["context"].append(
                SummaryItem(text=self._shorten(first_chunk.text), citation_ids=[first_chunk.chunk_id])
            )
        return DocumentSummary(**buckets)

    async def build_with_llm(
        self,
        document: NormalizedDocument,
        *,
        llm_client: LlmClient,
        max_chunks: int = 80,
    ) -> DocumentSummary:
        """Generate a real abstractive summary through an OpenAI-compatible LLM."""

        selected_chunks = self._select_prompt_chunks(document, max_chunks=max_chunks)
        allowed_ids = {chunk.chunk_id for chunk in selected_chunks}
        messages = [
            {
                "role": "system",
                "content": (
                    "Bạn là trợ lý AI cho cán bộ họp cấp tỉnh. "
                    "Chỉ tóm tắt dựa trên các chunks được cung cấp. "
                    "Mỗi ý bắt buộc có citation_ids lấy nguyên văn từ chunk_id có trong danh sách. "
                    "Không tự tạo citation_id, số trang, điều khoản hoặc sự kiện không có trong nguồn. "
                    "Không sao chép nguyên văn từng chunk; hãy viết lại thành nhận định tổng hợp, ngắn gọn, "
                    "dễ hiểu cho người chuẩn bị họp. "
                    "Trả về JSON hợp lệ theo schema: executive_summary, context, main_content, "
                    "decision_points, impact, risks. Mỗi field là mảng object {text, citation_ids}. "
                    "Bắt buộc điền đủ 4 mục context, main_content, decision_points, impact (mỗi mục ≥1 ý). "
                    "executive_summary viết 4-6 đoạn ngắn, mỗi đoạn 3-5 câu. "
                    "Không viết quá ngắn, không chỉ liệt kê đầu mục, không lặp nguyên văn điều khoản."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Hãy tạo bản tóm tắt tiếng Việt ngắn gọn, có cấu trúc, phục vụ chuẩn bị cuộc họp.\n\n"
                    f"Tên file: {document.file_name}\n"
                    f"Số trang: {document.page_count}\n"
                    "Chỉ được dùng các chunk_id sau trong citation_ids:\n"
                    + ", ".join(sorted(allowed_ids))
                    + "\n\nChunks:\n"
                    + self._chunks_payload(selected_chunks)
                ),
            },
        ]
        summary = await llm_client.call(messages, DocumentSummary)
        filtered = self._filter_invalid_citations(
            summary,
            document.citation_whitelist,
            preferred_ids=allowed_ids,
            fallback_chunk_id=selected_chunks[0].chunk_id if selected_chunks else None,
        )
        if self._is_effectively_empty(filtered):
            # OpenAI often invents citation IDs on large docs; keep prose and
            # backfill empty sections from the deterministic local summary.
            fallback = self.build(document)
            return self._merge_with_fallback(filtered, fallback)
        return filtered

    def _rank_chunks(
        self,
        chunks: list[DocumentChunk],
        keywords: tuple[str, ...],
    ) -> list[DocumentChunk]:
        return sorted(
            chunks,
            key=lambda chunk: (
                sum(keyword in chunk.text.lower() for keyword in keywords),
                len(chunk.text),
            ),
            reverse=True,
        )

    @staticmethod
    def _shorten(text: str, max_chars: int = 320) -> str:
        compact = " ".join(text.split())
        if len(compact) <= max_chars:
            return compact
        return compact[: max_chars - 3].rstrip() + "..."

    def _chunks_for_prompt(self, document: NormalizedDocument, max_chunks: int) -> str:
        return self._chunks_payload(self._select_prompt_chunks(document, max_chunks=max_chunks))

    def _chunks_payload(self, selected_chunks: list[DocumentChunk]) -> str:
        import json

        payload: list[dict[str, Any]] = []
        for chunk in selected_chunks:
            payload.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "page": chunk.page,
                    "chapter": chunk.chapter,
                    "section": chunk.section,
                    "article": chunk.article,
                    "clause": chunk.clause,
                    "point": chunk.point,
                    "text": self._shorten(chunk.text, max_chars=900),
                }
            )
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _select_prompt_chunks(
        self,
        document: NormalizedDocument,
        max_chunks: int,
    ) -> list[DocumentChunk]:
        if len(document.chunks) <= max_chunks:
            return document.chunks

        keyword_pool = tuple(
            sorted({keyword for _, keywords in self._rules for keyword in keywords})
        )
        ranked = self._rank_chunks(document.chunks, keyword_pool)
        selected = sorted(ranked[:max_chunks], key=lambda chunk: (chunk.page, chunk.chunk_id))
        return selected

    @staticmethod
    def _filter_invalid_citations(
        summary: DocumentSummary,
        whitelist: set[str],
        *,
        preferred_ids: set[str] | None = None,
        fallback_chunk_id: str | None = None,
    ) -> DocumentSummary:
        preferred = preferred_ids or set()

        def keep_valid(items: list[SummaryItem]) -> list[SummaryItem]:
            valid_items: list[SummaryItem] = []
            for item in items:
                text = item.text.strip()
                if not text:
                    continue
                citation_ids = [
                    citation_id
                    for citation_id in item.citation_ids
                    if citation_id in whitelist
                ]
                # Prefer citations that were actually shown to the LLM.
                preferred_hits = [citation_id for citation_id in citation_ids if citation_id in preferred]
                if preferred_hits:
                    citation_ids = preferred_hits
                elif not citation_ids and fallback_chunk_id:
                    citation_ids = [fallback_chunk_id]
                # Keep the prose even when the model invented bad citation IDs.
                valid_items.append(
                    SummaryItem(
                        text=text,
                        citation_ids=list(dict.fromkeys(citation_ids)),
                    )
                )
            return valid_items

        return DocumentSummary(
            executive_summary=keep_valid(summary.executive_summary),
            context=keep_valid(summary.context),
            main_content=keep_valid(summary.main_content),
            decision_points=keep_valid(summary.decision_points),
            impact=keep_valid(summary.impact),
            risks=keep_valid(summary.risks),
        )

    @staticmethod
    def _is_effectively_empty(summary: DocumentSummary) -> bool:
        return not any(
            (
                summary.executive_summary,
                summary.context,
                summary.main_content,
                summary.decision_points,
                summary.impact,
            )
        )

    @staticmethod
    def _merge_with_fallback(
        primary: DocumentSummary,
        fallback: DocumentSummary,
    ) -> DocumentSummary:
        def pick(field: str) -> list[SummaryItem]:
            values = getattr(primary, field) or getattr(fallback, field)
            return list(values)

        return DocumentSummary(
            executive_summary=pick("executive_summary"),
            context=pick("context"),
            main_content=pick("main_content"),
            decision_points=pick("decision_points"),
            impact=pick("impact"),
            risks=pick("risks"),
        )
