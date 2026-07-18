"""Rule-based meeting intelligence for the local MVP demo.

The production system should replace these heuristics with a Vietnamese LLM and
retrieval pipeline. This module keeps the same output shape so the app can be
demoed and tested without an external API key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING, Iterable, Sequence

if TYPE_CHECKING:
    from pipeline.processor import ProcessedDocument


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


class MeetingIntelligenceEngine:
    """Create summary, terminology, questions, and grounded Q&A output."""

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
        chunks = self._build_chunks(document)
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
        context = self._pick(sentences, ("cấu trúc", "bối cảnh", "gồm", "mục tiêu"), 3)
        main_content = self._pick(sentences, ("nội dung", "phần", "điểm", "môn", "câu hỏi"), 5)
        decision_points = self._pick(
            sentences,
            ("chọn", "quyết định", "hình thức", "thời gian", "tổng điểm"),
            4,
        )
        impact = self._pick(
            sentences,
            ("đánh giá", "tỷ trọng", "vận dụng", "hiểu", "biết", "tác động"),
            4,
        )
        risks = self._pick(
            sentences,
            ("lưu ý", "rủi ro", "chưa", "cần", "phải", "bắt buộc"),
            4,
        )

        return MeetingSummary(
            context=context or ["Tài liệu cần được xem xét nhanh trước cuộc họp để nắm nội dung chính."],
            main_content=main_content,
            decision_points=decision_points,
            impact=impact,
            risks=risks or ["Cần kiểm tra kỹ các mốc thời gian, tiêu chí đánh giá và phần nội dung bắt buộc."],
        )

    def detect_terms(self, chunks: Sequence[_Chunk], minimum: int = 10) -> list[TermExplanation]:
        full_text = "\n".join(chunk.text for chunk in chunks)
        normalized_text = full_text.lower()
        terms: list[TermExplanation] = []

        for term, explanation in self._TERM_DICTIONARY.items():
            if term in normalized_text:
                matching_chunks = [chunk for chunk in chunks if term in chunk.text.lower()]
                pages = sorted({chunk.page_number for chunk in matching_chunks})
                evidence = self._shorten(matching_chunks[0].text if matching_chunks else term)
                terms.append(
                    TermExplanation(
                        term=term,
                        explanation=explanation,
                        pages=pages,
                        evidence=evidence,
                    )
                )

        if len(terms) < minimum:
            terms.extend(self._extract_candidate_terms(chunks, existing={term.term for term in terms}))

        return terms[: max(minimum, len(terms))]

    def suggest_questions(self, chunks: Sequence[_Chunk]) -> list[SuggestedQuestion]:
        top_chunks = self._rank_chunks(chunks)[:5]
        citation = [f"Trang {chunk.page_number}" for chunk in top_chunks[:2]]

        templates = [
            (
                "Nội dung nào là bắt buộc phải quyết định hoặc thống nhất trong cuộc họp?",
                "Giúp chủ tọa tách phần cần ra quyết định khỏi phần chỉ để tham khảo.",
            ),
            (
                "Các tiêu chí, tỷ trọng hoặc căn cứ đánh giá đã đủ rõ để triển khai chưa?",
                "Làm rõ cách đo lường kết quả và tránh hiểu khác nhau giữa các đơn vị.",
            ),
            (
                "Những nhóm đối tượng hoặc đơn vị nào chịu tác động trực tiếp từ nội dung này?",
                "Giúp đánh giá ảnh hưởng thực tế trước khi thông qua hoặc giao nhiệm vụ.",
            ),
            (
                "Có điểm nào cần bổ sung căn cứ pháp lý, dữ liệu hoặc tài liệu liên quan không?",
                "Giảm rủi ro văn bản thiếu cơ sở khi đưa vào thực hiện.",
            ),
            (
                "Rủi ro lớn nhất nếu triển khai theo nội dung hiện tại là gì và ai chịu trách nhiệm xử lý?",
                "Buộc thảo luận về trách nhiệm, tiến độ và phương án xử lý tình huống.",
            ),
        ]
        return [
            SuggestedQuestion(question=question, rationale=rationale, citations=citation)
            for question, rationale in templates
        ]

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

        chunks = self._build_chunks(document)
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
                chunks.append(_Chunk(page_number=page.page_number, text=paragraph))
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
                sum(keyword in chunk.text.lower() for keyword in self._IMPORTANT_KEYWORDS),
                len(chunk.text),
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
            chunk_text = chunk.text.lower()
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
            chunk_text = chunk.text.lower()
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

    def _extract_candidate_terms(
        self,
        chunks: Sequence[_Chunk],
        existing: set[str],
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
                        explanation="Thuật ngữ/cụm nội dung quan trọng được trích từ tài liệu; cần giải thích theo ngữ cảnh văn bản.",
                        pages=[chunk.page_number],
                        evidence=self._shorten(chunk.text),
                    )
                )
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
    def _shorten(text: str, max_chars: int = 220) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= max_chars:
            return compact
        return f"{compact[: max_chars - 3].rstrip()}..."
