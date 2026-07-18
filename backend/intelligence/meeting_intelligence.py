"""Rule-based meeting intelligence for the local MVP demo.

The production system should replace these heuristics with a Vietnamese LLM and
retrieval pipeline. This module keeps the same output shape so the app can be
demoed and tested without an external API key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import unicodedata
from typing import TYPE_CHECKING, Iterable, Sequence

if TYPE_CHECKING:
    from backend.pipeline.processor import ProcessedDocument


@dataclass(frozen=True)
class MeetingSummary:
    """Structured summary required by the challenge brief."""

    context: list[str]
    main_content: list[str]
    decision_points: list[str]
    impact: list[str]
    risks: list[str]


@dataclass(frozen=True)
class TermExplanation:
    """A specialized term, short explanation, and where it appears."""

    term: str
    explanation: str
    pages: list[int]
    evidence: str


@dataclass(frozen=True)
class SuggestedQuestion:
    """A question officials should prepare before the meeting."""

    question: str
    rationale: str
    citations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GroundedAnswer:
    """Answer grounded in document chunks with page citations."""

    question: str
    answer: str
    citations: list[str]


@dataclass(frozen=True)
class MeetingIntelligenceReport:
    """Complete MVP output for one uploaded document."""

    summary: MeetingSummary
    terms: list[TermExplanation]
    questions: list[SuggestedQuestion]
    sample_answer: GroundedAnswer | None


@dataclass(frozen=True)
class _Chunk:
    page_number: int
    text: str
    normalized_text: str
    word_count: int


class MeetingIntelligenceEngine:
    """Create summary, terminology, questions, and grounded Q&A output."""

    _TERM_LIMIT = 100
    _QUESTION_CITATION_LIMIT = 6

    _TERM_DICTIONARY: dict[str, str] = {
        "nghị quyết": "Văn bản thể hiện quyết định hoặc chủ trương được cơ quan có thẩm quyền thông qua.",
        "quyết định": "Văn bản hành chính dùng để ban hành một chủ trương, nhiệm vụ hoặc biện pháp cụ thể.",
        "ủy ban nhân dân": "Cơ quan hành chính nhà nước ở địa phương, chịu trách nhiệm tổ chức thi hành pháp luật.",
        "hội đồng nhân dân": "Cơ quan quyền lực nhà nước ở địa phương, đại diện cho ý chí và nguyện vọng của nhân dân.",
        "tờ trình": "Văn bản đề xuất một nội dung để cấp có thẩm quyền xem xét, quyết định.",
        "đề án": "Tài liệu trình bày mục tiêu, giải pháp, nguồn lực và lộ trình thực hiện một chương trình.",
        "dự thảo": "Phiên bản văn bản chưa được ban hành chính thức, còn trong quá trình lấy ý kiến hoặc chỉnh sửa.",
        "căn cứ pháp lý": "Các văn bản luật, nghị định, thông tư hoặc quy định làm cơ sở cho nội dung đề xuất.",
        "ngân sách": "Nguồn kinh phí được phân bổ để thực hiện nhiệm vụ, chương trình hoặc dự án.",
        "lộ trình": "Trình tự thời gian và các mốc triển khai một nhiệm vụ hoặc chính sách.",
        "trách nhiệm": "Phần việc và nghĩa vụ được giao cho cơ quan, tổ chức hoặc cá nhân thực hiện.",
        "tác động": "Ảnh hưởng dự kiến của chính sách hoặc quyết định tới người dân, ngân sách, tổ chức hoặc xã hội.",
        "rủi ro": "Yếu tố có thể khiến việc triển khai không đạt mục tiêu, chậm tiến độ hoặc phát sinh chi phí.",
        "tự luận": "Dạng câu hỏi yêu cầu người làm trình bày lập luận, phân tích và quan điểm bằng văn viết.",
        "trắc nghiệm": "Dạng câu hỏi có các lựa chọn trả lời, thường dùng để kiểm tra phạm vi kiến thức rộng.",
        "nghị luận xã hội": "Dạng bài phân tích, bàn luận về một vấn đề xã hội, chính trị, kinh tế hoặc văn hóa.",
        "kinh tế học vĩ mô": "Lĩnh vực nghiên cứu các biến số lớn của nền kinh tế như tăng trưởng, lạm phát và chính sách.",
        "triết học": "Lĩnh vực nghiên cứu các nguyên lý chung về thế giới quan, phương pháp luận và nhận thức.",
        "lý luận nhà nước và pháp luật": "Môn học về bản chất, vai trò, tổ chức nhà nước và hệ thống pháp luật.",
        "tỷ trọng đánh giá": "Tỷ lệ phân bổ các mức độ hoặc tiêu chí được dùng để chấm điểm, đánh giá.",
        "vận dụng": "Mức độ yêu cầu người học áp dụng kiến thức để xử lý tình huống hoặc giải quyết vấn đề.",
    }

    _IMPORTANT_KEYWORDS = (
        "cấu trúc",
        "mục tiêu",
        "nội dung",
        "quy định",
        "điểm",
        "thời gian",
        "hình thức",
        "trách nhiệm",
        "tác động",
        "ngân sách",
        "rủi ro",
        "đề xuất",
        "triển khai",
        "đánh giá",
    )

    _DECISION_STRONG_SIGNALS = (
        "quyet dinh",
        "thong qua",
        "phe duyet",
        "lua chon",
        "ket luan",
        "cho y kien",
        "xin y kien",
        "trinh",
        "de nghi",
        "de xuat",
        "phuong an",
        "chu truong",
        "giao",
        "phan cong",
        "trach nhiem",
        "thoi han",
        "lo trinh",
        "kinh phi",
        "nguon luc",
        "ngan sach",
        "rui ro",
        "xu ly",
        "chi dao",
    )

    _DECISION_ACTION_SIGNALS = (
        "can",
        "phai",
        "bat buoc",
        "yeu cau",
        "bao dam",
        "dam bao",
        "to chuc thuc hien",
        "trien khai",
        "ban hanh",
    )

    _DECISION_WEAK_SIGNALS = (
        "la gi",
        "khai niem",
        "dinh nghia",
        "tong quan",
        "gioi thieu",
        "bao gom",
        "noi dung chinh",
        "ket qua",
        "doanh thu",
        "tang truong",
    )

    _QUESTION_STOPWORDS = {
        "anh",
        "bao",
        "chị",
        "cho",
        "của",
        "các",
        "cần",
        "hôm",
        "hãy",
        "không",
        "liệu",
        "nay",
        "nào",
        "này",
        "người",
        "nhiêu",
        "những",
        "theo",
        "trong",
        "tài",
        "và",
        "về",
    }

    def build_report(
        self,
        document: ProcessedDocument,
        sample_question: str | None = None,
    ) -> MeetingIntelligenceReport:
        chunks = self._get_chunks(document)
        return MeetingIntelligenceReport(
            summary=self.summarize(chunks),
            terms=self.detect_terms(chunks, minimum=10),
            questions=self.suggest_questions(chunks),
            sample_answer=self.answer_question(sample_question, chunks)
            if sample_question
            else None,
        )

    def summarize(self, chunks: Sequence[_Chunk]) -> MeetingSummary:
        sentences = self._rank_sentences(chunks)
        context_items = self._pick(sentences, ("cấu trúc", "bối cảnh", "gồm", "mục tiêu"), 3)
        main_content_items = self._pick(
            sentences,
            ("nội dung", "phần", "điểm", "môn", "câu hỏi"),
            5,
        )
        decision_items = self._pick_decision_points(chunks, 4)
        impact_items = self._pick(
            sentences,
            ("đánh giá", "tỷ trọng", "vận dụng", "hiểu", "biết", "tác động"),
            4,
        )
        risk_items = self._pick(
            sentences,
            ("lưu ý", "rủi ro", "chưa", "cần", "phải", "bắt buộc"),
            4,
        )

        ranked_fallback = list(sentences[:4])
        context = self._compose_summary_section(
            context_items or ranked_fallback[:3],
            "Tài liệu đặt ra bối cảnh và phạm vi xem xét như sau:",
        )
        main_content = self._compose_summary_section(
            main_content_items or ranked_fallback,
            "Các nội dung cốt lõi được trình bày gồm:",
        )
        decision_points = self._compose_summary_section(
            decision_items,
            "Các vấn đề cần được xem xét, kết luận hoặc giao trách nhiệm gồm:",
        )
        impact = self._compose_summary_section(
            impact_items,
            "Các tác động, hệ quả và lưu ý triển khai được tài liệu đề cập gồm:",
        )
        risks = self._compose_summary_section(
            risk_items,
            "Các rủi ro hoặc điều kiện cần kiểm tra thêm gồm:",
        )

        return MeetingSummary(
            context=context,
            main_content=main_content,
            decision_points=decision_points,
            impact=impact,
            risks=risks,
        )

    def _compose_summary_section(
        self,
        items: Sequence[str],
        lead: str,
        max_chars: int = 650,
    ) -> list[str]:
        if not items:
            return []

        pages: list[int] = []
        clauses: list[str] = []
        seen: set[str] = set()
        for item in items:
            for page in re.findall(r"Trang\s+(\d+)", item, flags=re.IGNORECASE):
                page_number = int(page)
                if page_number not in pages:
                    pages.append(page_number)
            clause = re.sub(r"\s*\(Trang\s+\d+\)\s*$", "", item, flags=re.IGNORECASE)
            clause = re.sub(r"\s+", " ", clause).strip(" .;:")
            key = clause.casefold()
            if clause and key not in seen:
                clauses.append(clause)
                seen.add(key)

        if not clauses:
            return []

        source_label = ", ".join(f"Trang {page}" for page in pages[:6])
        suffix = f" ({source_label})" if source_label else ""
        available = max(80, max_chars - len(lead) - len(suffix) - 2)
        body = self._shorten("; ".join(clauses), max_chars=available).rstrip(" .")
        return [f"{lead} {body}.{suffix}".strip()]

    def detect_terms(
        self,
        chunks: Sequence[_Chunk],
        minimum: int = 10,
        limit: int = _TERM_LIMIT,
    ) -> list[TermExplanation]:
        normalized_text = "\n".join(chunk.normalized_text for chunk in chunks)
        ranked_terms: list[tuple[int, TermExplanation]] = []

        for term, explanation in self._TERM_DICTIONARY.items():
            if term in normalized_text:
                matching_chunks = [chunk for chunk in chunks if term in chunk.normalized_text]
                representative = self._representative_term_chunk(term, matching_chunks)
                page = representative.page_number if representative is not None else 1
                evidence = self._shorten(representative.text if representative is not None else term)
                ranked_terms.append(
                    (
                        self._term_importance_score(term, matching_chunks),
                        TermExplanation(
                            term=term,
                            explanation=explanation,
                            pages=[page],
                            evidence=evidence,
                        ),
                    )
                )

        terms = [term for _, term in sorted(ranked_terms, key=lambda item: item[0], reverse=True)]

        if len(terms) < minimum:
            terms.extend(
                self._extract_candidate_terms(
                    chunks,
                    existing={term.term for term in terms},
                    limit=max(0, minimum - len(terms)),
                )
            )

        return terms[:limit]

    def _representative_term_chunk(
        self,
        term: str,
        chunks: Sequence[_Chunk],
    ) -> _Chunk | None:
        if not chunks:
            return None
        return max(chunks, key=lambda chunk: self._term_chunk_score(term, chunk))

    def _term_importance_score(self, term: str, chunks: Sequence[_Chunk]) -> int:
        if not chunks:
            return 0
        normalized_term = self._normalize_for_matching(term)
        occurrence_count = sum(chunk.normalized_text.count(term) for chunk in chunks)
        page_count = len({chunk.page_number for chunk in chunks})
        signal_score = 0
        for signal in (
            *self._DECISION_STRONG_SIGNALS,
            *self._DECISION_ACTION_SIGNALS,
            "can cu phap ly",
            "muc tieu",
            "tac dong",
            "danh gia",
        ):
            if signal in normalized_term:
                signal_score += 4
        return occurrence_count * 3 + min(page_count, 5) * 2 + signal_score

    def _term_chunk_score(self, term: str, chunk: _Chunk) -> int:
        text = chunk.normalized_text
        normalized_text = self._normalize_for_matching(chunk.text)
        score = text.count(term) * 4
        score += sum(2 for signal in self._DECISION_STRONG_SIGNALS if signal in normalized_text)
        score += sum(1 for keyword in self._IMPORTANT_KEYWORDS if keyword in text)
        score += min(chunk.word_count // 60, 3)
        return score

    def suggest_questions(self, chunks: Sequence[_Chunk]) -> list[SuggestedQuestion]:
        anchors: list[tuple[str, int]] = []
        seen: set[str] = set()
        for chunk in self._rank_chunks(chunks):
            for sentence in self._split_sentences(chunk.text):
                anchor = self._shorten(re.sub(r"\s+", " ", sentence).strip(), 120)
                normalized = self._normalize_for_matching(anchor)
                if len(anchor) < 20 or normalized in seen:
                    continue
                seen.add(normalized)
                anchors.append((anchor, chunk.page_number))
                if len(anchors) >= 5:
                    break
            if len(anchors) >= 5:
                break

        if not anchors:
            return []

        templates = (
            (
                "Đối với nội dung “{anchor}”, dữ liệu hoặc tiêu chí nào chứng minh đề xuất này đủ cơ sở để quyết định?",
                "Kiểm tra căn cứ của chính nội dung được nêu tại trang {page}, thay vì thảo luận một giả định chung.",
            ),
            (
                "Khi thực hiện nội dung “{anchor}”, đánh đổi lớn nhất về nguồn lực, tiến độ hoặc chất lượng là gì?",
                "Làm rõ hệ quả triển khai của nội dung cụ thể tại trang {page} trước khi thống nhất phương án.",
            ),
            (
                "Nội dung “{anchor}” đã xác định rõ đơn vị chịu trách nhiệm và mốc hoàn thành hay chưa?",
                "Gắn luận điểm tại trang {page} với trách nhiệm có thể kiểm tra sau cuộc họp.",
            ),
            (
                "Giả định quan trọng nào đứng sau nội dung “{anchor}”, và phương án sẽ thay đổi ra sao nếu giả định đó không đúng?",
                "Kiểm tra độ bền của luận điểm tại trang {page} trước các điều kiện chưa chắc chắn.",
            ),
            (
                "Với nội dung “{anchor}”, chỉ số và thời điểm nào sẽ được dùng để kết luận việc triển khai đạt kết quả?",
                "Chuyển nội dung tại trang {page} thành tiêu chí giám sát cụ thể sau quyết định.",
            ),
        )
        questions: list[SuggestedQuestion] = []
        for index, (template, rationale) in enumerate(templates):
            anchor, page = anchors[index % len(anchors)]
            citation_pages = self._question_support_pages(
                anchor,
                chunks,
                primary_page=page,
            )
            questions.append(
                SuggestedQuestion(
                    question=template.format(anchor=anchor),
                    rationale=rationale.format(page=page),
                    citations=[f"Trang {citation_page}" for citation_page in citation_pages],
                )
            )
        return questions

    def _question_support_pages(
        self,
        anchor: str,
        chunks: Sequence[_Chunk],
        *,
        primary_page: int,
    ) -> list[int]:
        """Trace the source pages that directly support a question premise.

        The primary page contains the sentence used as the question anchor.
        Additional pages are retained only when they share enough meaningful
        terms with that anchor, preventing the previous single-page hard-code
        without attaching unrelated citations to every question.
        """

        anchor_terms = self._extract_question_terms(anchor)
        if not anchor_terms:
            return [primary_page]

        minimum_overlap = max(2, min(4, (len(anchor_terms) + 2) // 3))
        ranked_pages: list[tuple[int, int]] = []
        best_score_by_page: dict[int, int] = {}
        for chunk in chunks:
            chunk_terms = self._extract_question_terms(chunk.text)
            score = len(anchor_terms.intersection(chunk_terms))
            if chunk.page_number != primary_page and score < minimum_overlap:
                continue
            best_score_by_page[chunk.page_number] = max(
                score,
                best_score_by_page.get(chunk.page_number, 0),
            )

        for page, score in best_score_by_page.items():
            if page != primary_page:
                ranked_pages.append((score, page))
        ranked_pages.sort(key=lambda item: (-item[0], item[1]))

        pages = [primary_page]
        pages.extend(page for _, page in ranked_pages)
        return pages[: self._QUESTION_CITATION_LIMIT]

    def answer_question_from_document(
        self,
        document: ProcessedDocument,
        question: str,
        max_chunks: int = 4,
    ) -> GroundedAnswer:
        """Answer strictly from the uploaded document.

        The chatbot uses this method so it does not answer from outside
        knowledge. If no evidence is retrieved, it explicitly says so.
        """

        chunks = self._get_chunks(document)
        question_terms = self._extract_question_terms(question)
        if not question_terms:
            return GroundedAnswer(
                question=question,
                answer=(
                    "Bạn vui lòng đặt câu hỏi cụ thể hơn. Chatbot này chỉ trả lời "
                    "dựa trên nội dung PDF đã upload."
                ),
                citations=[],
            )

        min_score = 2 if len(question_terms) >= 3 else 1
        scored_chunks = self._score_chunks_by_terms(question_terms, chunks)
        selected = [
            chunk
            for score, chunk in scored_chunks[:max_chunks]
            if score >= min_score
        ]
        if not selected:
            return GroundedAnswer(
                question=question,
                answer=(
                    "Không tìm thấy thông tin đủ liên quan trong PDF đã upload. "
                    "Chatbot này không dùng kiến thức bên ngoài tài liệu."
                ),
                citations=[],
            )

        evidence_lines = [
            f"- {self._shorten(chunk.text, max_chars=360)}"
            for chunk in selected
        ]
        citations = list(dict.fromkeys(f"Trang {chunk.page_number}" for chunk in selected))
        answer = (
            "Dựa trên nội dung PDF đã upload, các đoạn liên quan cho thấy:\n"
            + "\n".join(evidence_lines)
            + "\n\nKết luận ngắn: câu trả lời phía trên chỉ được rút ra từ các trang được trích dẫn."
        )
        return GroundedAnswer(question=question, answer=answer, citations=citations)

    def answer_question(self, question: str, chunks: Sequence[_Chunk]) -> GroundedAnswer:
        scored_chunks = self._score_chunks_for_question(question, chunks)
        selected = [chunk for score, chunk in scored_chunks[:3] if score > 0]
        if not selected:
            selected = self._rank_chunks(chunks)[:2]

        evidence = " ".join(self._shorten(chunk.text, max_chars=280) for chunk in selected)
        citations = [f"Trang {chunk.page_number}" for chunk in selected]
        answer = (
            f"Dựa trên các đoạn liên quan trong tài liệu: {evidence} "
            "Cần đối chiếu thêm toàn văn nếu đây là câu hỏi dùng để ra quyết định chính thức."
        )
        return GroundedAnswer(question=question, answer=answer, citations=citations)

    def _build_chunks(self, document: ProcessedDocument) -> list[_Chunk]:
        chunks: list[_Chunk] = []
        for page in document.stitched_pages:
            for paragraph in self._split_paragraphs(page.content):
                chunks.append(
                    _Chunk(
                        page_number=page.page_number,
                        text=paragraph,
                        normalized_text=paragraph.lower(),
                        word_count=len(paragraph.split()),
                    )
                )
        return chunks

    def extract_chunks(self, document: ProcessedDocument) -> list[_Chunk]:
        """Expose the chunk builder so orchestration can cache once."""

        return self._build_chunks(document)

    def _get_chunks(self, document: ProcessedDocument) -> list[_Chunk]:
        cached_chunks = getattr(document, "chunks", None)
        if cached_chunks:
            return cached_chunks

        chunks = self._build_chunks(document)
        try:
            document.chunks = chunks
        except Exception:  # pragma: no cover - document may be immutable in tests
            pass
        return chunks

    def _rank_sentences(self, chunks: Sequence[_Chunk]) -> list[str]:
        candidates: list[tuple[int, str]] = []
        for chunk in chunks:
            for sentence in self._split_sentences(chunk.text):
                score = sum(2 for keyword in self._IMPORTANT_KEYWORDS if keyword in sentence.lower())
                score += min(len(sentence) // 80, 3)
                candidates.append((score, f"{sentence} (Trang {chunk.page_number})"))
        return [sentence for _, sentence in sorted(candidates, reverse=True)]

    def _rank_chunks(self, chunks: Sequence[_Chunk]) -> list[_Chunk]:
        return sorted(
            chunks,
            key=lambda chunk: (
                sum(keyword in chunk.normalized_text for keyword in self._IMPORTANT_KEYWORDS),
                chunk.word_count,
            ),
            reverse=True,
        )

    def _score_chunks_for_question(
        self,
        question: str,
        chunks: Sequence[_Chunk],
    ) -> list[tuple[int, _Chunk]]:
        question_terms = {
            term
            for term in re.findall(r"[\wÀ-ỹ]+", question.lower())
            if len(term) >= 4
        }
        scored: list[tuple[int, _Chunk]] = []
        for chunk in chunks:
            chunk_text = chunk.normalized_text
            score = sum(1 for term in question_terms if term in chunk_text)
            score += sum(1 for keyword in self._IMPORTANT_KEYWORDS if keyword in chunk_text)
            scored.append((score, chunk))
        return sorted(scored, key=lambda item: (item[0], len(item[1].text)), reverse=True)

    def _extract_question_terms(self, question: str) -> set[str]:
        terms: set[str] = set()
        for term in re.findall(r"[\wÀ-ỹ]+", question.lower()):
            if len(term) < 3 or term in self._QUESTION_STOPWORDS:
                continue
            terms.add(term)
        return terms

    def _score_chunks_by_terms(
        self,
        question_terms: set[str],
        chunks: Sequence[_Chunk],
    ) -> list[tuple[int, _Chunk]]:
        scored: list[tuple[int, _Chunk]] = []
        for chunk in chunks:
            chunk_text = chunk.normalized_text
            score = sum(1 for term in question_terms if term in chunk_text)
            scored.append((score, chunk))
        return sorted(scored, key=lambda item: (item[0], len(item[1].text)), reverse=True)

    def _pick(
        self,
        sentences: Sequence[str],
        keywords: Iterable[str],
        limit: int,
    ) -> list[str]:
        picked: list[str] = []
        seen: set[str] = set()
        for sentence in sentences:
            lower_sentence = sentence.lower()
            if not any(keyword in lower_sentence for keyword in keywords):
                continue
            compact = re.sub(r"\s+", " ", sentence).strip()
            if compact in seen:
                continue
            picked.append(compact)
            seen.add(compact)
            if len(picked) >= limit:
                break
        return picked

    def _pick_decision_points(self, chunks: Sequence[_Chunk], limit: int) -> list[str]:
        candidates: list[tuple[int, int, str]] = []
        seen: set[str] = set()
        for chunk in chunks:
            for sentence in self._split_sentences(chunk.text):
                compact = re.sub(r"\s+", " ", sentence).strip()
                if compact in seen:
                    continue
                seen.add(compact)
                score = self._decision_score(compact)
                if score < 3:
                    continue
                candidates.append((score, -len(compact), f"{compact} (Trang {chunk.page_number})"))
        ranked = sorted(candidates, reverse=True)
        return [sentence for _, _, sentence in ranked[:limit]]

    def _decision_score(self, sentence: str) -> int:
        normalized = self._normalize_for_matching(sentence)
        score = 0
        score += sum(3 for signal in self._DECISION_STRONG_SIGNALS if signal in normalized)
        score += sum(2 for signal in self._DECISION_ACTION_SIGNALS if signal in normalized)
        score -= sum(2 for signal in self._DECISION_WEAK_SIGNALS if signal in normalized)
        if "?" in sentence:
            score += 1
        if re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b20\d{2}\b", normalized):
            score += 1
        if 80 <= len(sentence) <= 420:
            score += 1
        return score

    def _extract_candidate_terms(
        self,
        chunks: Sequence[_Chunk],
        existing: set[str],
        limit: int,
    ) -> list[TermExplanation]:
        phrase_pattern = re.compile(r"\b[A-ZÀ-Ỹ][\wÀ-ỹ]*(?:\s+[A-ZÀ-Ỹ]?[.\wÀ-ỹ]+){1,5}")
        candidates: list[TermExplanation] = []
        for chunk in chunks:
            for match in phrase_pattern.findall(chunk.text):
                term = match.strip(" .,:;").lower()
                if len(term) < 8 or term in existing:
                    continue
                existing.add(term)
                candidates.append(
                    TermExplanation(
                        term=term,
                        explanation=(
                            f"Trong tài liệu, “{term}” được dùng trong ngữ cảnh: "
                            f"{self._shorten(chunk.text, max_chars=160)}"
                        ),
                        pages=[chunk.page_number],
                        evidence=self._shorten(chunk.text),
                    )
                )
                if len(candidates) >= limit:
                    return candidates
        return candidates

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        return [
            paragraph.strip()
            for paragraph in re.split(r"\n{2,}", text)
            if paragraph.strip() and len(paragraph.strip()) > 20
        ]

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        return [sentence.strip() for sentence in raw_sentences if len(sentence.strip()) > 30]

    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        decomposed = unicodedata.normalize("NFD", text.casefold())
        without_accents = "".join(
            char for char in decomposed if unicodedata.category(char) != "Mn"
        )
        return without_accents.replace("đ", "d")

    @staticmethod
    def _shorten(text: str, max_chars: int = 220) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= max_chars:
            return compact
        return f"{compact[: max_chars - 3].rstrip()}..."
