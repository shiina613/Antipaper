"""Decision & Risk Radar built from normalized document chunks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.intelligence.contracts import DocumentChunk, NormalizedDocument
from src.llm import LlmClient


class DecisionRadarItem(BaseModel):
    """One evidence-backed decision/risk signal."""

    model_config = ConfigDict(extra="forbid")

    category: str
    finding: str
    confidence: float = Field(ge=0, le=1)
    citation_ids: list[str]

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            mapping = {
                "high": 0.9,
                "cao": 0.9,
                "medium": 0.6,
                "moderate": 0.6,
                "trung bình": 0.6,
                "low": 0.3,
                "thấp": 0.3,
            }
            if normalized in mapping:
                return mapping[normalized]
        return value


class DecisionRadar(BaseModel):
    """High-level meeting preparation radar."""

    model_config = ConfigDict(extra="forbid")

    decision_points: list[DecisionRadarItem] = Field(default_factory=list)
    legal_basis: list[DecisionRadarItem] = Field(default_factory=list)
    responsibilities: list[DecisionRadarItem] = Field(default_factory=list)
    deadlines: list[DecisionRadarItem] = Field(default_factory=list)
    resources: list[DecisionRadarItem] = Field(default_factory=list)
    risks: list[DecisionRadarItem] = Field(default_factory=list)
    open_questions: list[DecisionRadarItem] = Field(default_factory=list)


class DecisionRadarEngine:
    """Rule-based radar for the first vertical slice."""

    _rules: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        ("decision_points", "Vấn đề cần quyết định/thống nhất", ("quyết định", "phê duyệt", "thống nhất", "thông qua")),
        ("legal_basis", "Căn cứ pháp lý", ("căn cứ", "luật", "nghị định", "thông tư", "quy định", "điều ")),
        ("responsibilities", "Đơn vị/trách nhiệm thực hiện", ("trách nhiệm", "chủ trì", "phối hợp", "báo cáo", "thực hiện")),
        ("deadlines", "Thời hạn/lộ trình", ("thời hạn", "lộ trình", "giai đoạn", "ngày", "tháng", "quý", "năm")),
        ("resources", "Nguồn lực/ngân sách", ("ngân sách", "kinh phí", "nguồn lực", "nhân lực", "hạ tầng")),
        ("risks", "Rủi ro/điểm cần kiểm tra", ("rủi ro", "chưa", "thiếu", "khó khăn", "vướng mắc", "xung đột")),
        ("open_questions", "Điểm còn bỏ ngỏ", ("đề nghị", "cần làm rõ", "xem xét", "bổ sung", "lấy ý kiến")),
    )

    def build(self, document: NormalizedDocument, limit_per_category: int = 5) -> DecisionRadar:
        buckets: dict[str, list[DecisionRadarItem]] = {name: [] for name, _, _ in self._rules}
        for chunk in document.chunks:
            lower_text = chunk.text.lower()
            for field_name, category, keywords in self._rules:
                matches = [keyword for keyword in keywords if keyword in lower_text]
                if not matches:
                    continue
                if len(buckets[field_name]) >= limit_per_category:
                    continue
                confidence = min(0.95, 0.45 + 0.15 * len(matches))
                buckets[field_name].append(
                    DecisionRadarItem(
                        category=category,
                        finding=self._shorten(chunk.text),
                        confidence=confidence,
                        citation_ids=[chunk.chunk_id],
                    )
                )

        return DecisionRadar(**buckets)

    async def build_with_llm(
        self,
        document: NormalizedDocument,
        *,
        llm_client: LlmClient,
        max_chunks: int = 80,
    ) -> DecisionRadar:
        messages = [
            {
                "role": "system",
                "content": (
                    "Bạn là trợ lý phân tích hồ sơ họp cấp tỉnh. "
                    "Hãy tạo Decision & Risk Radar dựa CHỈ trên chunks được cung cấp. "
                    "Mỗi item bắt buộc có citation_ids lấy nguyên văn từ chunk_id. "
                    "Không tự tạo số trang, điều khoản, văn bản hoặc dữ kiện không có trong nguồn. "
                    "Trả JSON hợp lệ theo schema gồm các mảng: decision_points, legal_basis, "
                    "responsibilities, deadlines, resources, risks, open_questions. "
                    "Mỗi item có {category, finding, confidence, citation_ids}. "
                    "confidence BẮT BUỘC là số thực từ 0.0 đến 1.0, ví dụ 0.85; "
                    "không được dùng chuỗi như high, medium, low. "
                    "finding phải là nhận định có ích cho người đi họp: cần quyết định gì, "
                    "ai chịu trách nhiệm, căn cứ nào, hạn nào, nguồn lực nào, rủi ro nào, "
                    "điểm nào còn cần hỏi thêm. Không copy nguyên văn chunk dài."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Tên file: {document.file_name}\n"
                    f"Số trang: {document.page_count}\n"
                    "Chunks:\n"
                    + self._chunks_for_prompt(document, max_chunks=max_chunks)
                ),
            },
        ]
        radar = await llm_client.call(messages, DecisionRadar)
        return self._filter_invalid_citations(radar, document.citation_whitelist)

    @staticmethod
    def _shorten(text: str, max_chars: int = 260) -> str:
        compact = " ".join(text.split())
        if len(compact) <= max_chars:
            return compact
        return compact[: max_chars - 3].rstrip() + "..."

    def _chunks_for_prompt(self, document: NormalizedDocument, max_chunks: int) -> str:
        selected_chunks = self._select_prompt_chunks(document, max_chunks=max_chunks)
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
        import json

        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _select_prompt_chunks(
        self,
        document: NormalizedDocument,
        max_chunks: int,
    ) -> list[DocumentChunk]:
        if len(document.chunks) <= max_chunks:
            return document.chunks

        keyword_pool = tuple(sorted({keyword for _, _, keywords in self._rules for keyword in keywords}))
        ranked = sorted(
            document.chunks,
            key=lambda chunk: (
                sum(keyword in chunk.text.lower() for keyword in keyword_pool),
                len(chunk.text),
            ),
            reverse=True,
        )
        return sorted(ranked[:max_chunks], key=lambda chunk: (chunk.page, chunk.chunk_id))

    @staticmethod
    def _filter_invalid_citations(
        radar: DecisionRadar,
        whitelist: set[str],
    ) -> DecisionRadar:
        def keep_valid(items: list[DecisionRadarItem]) -> list[DecisionRadarItem]:
            valid_items: list[DecisionRadarItem] = []
            for item in items:
                citation_ids = [citation_id for citation_id in item.citation_ids if citation_id in whitelist]
                if citation_ids:
                    valid_items.append(
                        item.model_copy(update={"citation_ids": list(dict.fromkeys(citation_ids))})
                    )
            return valid_items

        return DecisionRadar(
            decision_points=keep_valid(radar.decision_points),
            legal_basis=keep_valid(radar.legal_basis),
            responsibilities=keep_valid(radar.responsibilities),
            deadlines=keep_valid(radar.deadlines),
            resources=keep_valid(radar.resources),
            risks=keep_valid(radar.risks),
            open_questions=keep_valid(radar.open_questions),
        )
