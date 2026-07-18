"""Deterministic terms/questions pack over NormalizedDocument for the API v1 demo."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .contracts import (
    NormalizedDocument,
    SuggestedQuestion,
    TermExplanation,
)


_TERM_DICTIONARY: dict[str, str] = {
    "nghị quyết": "Văn bản thể hiện quyết định hoặc chủ trương được cơ quan có thẩm quyền thông qua.",
    "quyết định": "Văn bản hành chính dùng để ban hành một chủ trương, nhiệm vụ hoặc biện pháp cụ thể.",
    "ủy ban nhân dân": "Cơ quan hành chính nhà nước ở địa phương, chịu trách nhiệm tổ chức thi hành pháp luật.",
    "hội đồng nhân dân": "Cơ quan quyền lực nhà nước ở địa phương, đại diện cho ý chí và nguyện vọng của nhân dân.",
    "căn cứ pháp lý": "Các văn bản luật, nghị định, thông tư hoặc quy định làm cơ sở cho nội dung đề xuất.",
    "trách nhiệm": "Phần việc và nghĩa vụ được giao cho cơ quan, tổ chức hoặc cá nhân thực hiện.",
    "tác động": "Ảnh hưởng dự kiến của chính sách hoặc quyết định tới người dân, tổ chức hoặc xã hội.",
    "rủi ro": "Yếu tố có thể khiến việc triển khai không đạt mục tiêu hoặc phát sinh hậu quả bất lợi.",
    "hôn nhân": "Quan hệ giữa vợ và chồng sau khi kết hôn theo quy định của pháp luật.",
    "gia đình": "Tập hợp những người gắn bó với nhau bởi hôn nhân, quan hệ huyết thống hoặc nuôi dưỡng.",
    "kết hôn": "Việc nam và nữ xác lập quan hệ vợ chồng theo điều kiện và thủ tục luật định.",
    "ly hôn": "Chấm dứt quan hệ vợ chồng theo bản án, quyết định có hiệu lực của Tòa án.",
    "nuôi con nuôi": "Việc xác lập quan hệ cha, mẹ và con giữa người nhận nuôi và người được nhận nuôi.",
    "an ninh mạng": "Bảo đảm hoạt động trên không gian mạng không gây phương hại đến an ninh quốc gia, trật tự xã hội.",
    "an toàn thông tin mạng": "Bảo vệ thông tin và hệ thống thông tin trên mạng khỏi truy cập, sử dụng, phá hoại trái phép.",
    "hệ thống thông tin quan trọng về an ninh quốc gia": "Hệ thống thông tin nếu bị phá hoại hoặc lộ lọt có thể ảnh hưởng nghiêm trọng đến an ninh quốc gia.",
    "không gian mạng": "Môi trường thông tin được tạo ra bởi mạng máy tính và hạ tầng kỹ thuật số liên kết.",
    "dữ liệu cá nhân": "Thông tin dưới dạng ký hiệu, chữ viết, số, hình ảnh hoặc âm thanh gắn với một cá nhân xác định.",
    "xử lý vi phạm hành chính": "Hoạt động áp dụng biện pháp xử lý đối với hành vi vi phạm hành chính theo luật định.",
    "tố tụng dân sự": "Trình tự, thủ tục giải quyết vụ việc dân sự tại Tòa án.",
}


@dataclass(frozen=True)
class LocalIntelligencePack:
    terms: list[TermExplanation]
    suggested_questions: list[SuggestedQuestion]


def build_local_intelligence_pack(
    document: NormalizedDocument,
    *,
    minimum_terms: int = 10,
    minimum_questions: int = 5,
) -> LocalIntelligencePack:
    return LocalIntelligencePack(
        terms=detect_terms(document, minimum=minimum_terms),
        suggested_questions=suggest_questions(document, minimum=minimum_questions),
    )


def detect_terms(document: NormalizedDocument, *, minimum: int = 10) -> list[TermExplanation]:
    terms: list[TermExplanation] = []
    seen: set[str] = set()
    joined = "\n".join(chunk.text.casefold() for chunk in document.chunks)

    for term, explanation in _TERM_DICTIONARY.items():
        if term not in joined:
            continue
        citation_ids = [
            chunk.chunk_id
            for chunk in document.chunks
            if term in chunk.text.casefold()
        ][:3]
        if not citation_ids:
            continue
        terms.append(
            TermExplanation(
                term=term,
                explanation=explanation,
                citation_ids=citation_ids,
            )
        )
        seen.add(term)

    if len(terms) < minimum:
        for term, explanation, citation_ids in _extract_candidate_terms(document, existing=seen):
            terms.append(
                TermExplanation(
                    term=term,
                    explanation=explanation,
                    citation_ids=citation_ids,
                )
            )
            if len(terms) >= minimum:
                break

    return terms[: max(minimum, len(terms))]


def suggest_questions(
    document: NormalizedDocument,
    *,
    minimum: int = 5,
) -> list[SuggestedQuestion]:
    ranked = _rank_chunks(document.chunks)
    if not ranked:
        return []

    anchors = ranked[:8]
    citation_pool = [chunk.chunk_id for chunk in anchors]

    templates: list[tuple[str, str, list[str]]] = []
    article_chunks = [chunk for chunk in anchors if chunk.article]
    if article_chunks:
        sample = article_chunks[0]
        templates.append(
            (
                f"{sample.article} quy định gì và điều kiện áp dụng cụ thể là gì?",
                "Buộc làm rõ phạm vi điều chỉnh trước khi thảo luận triển khai.",
                [sample.chunk_id],
            )
        )
    decision_chunks = [
        chunk
        for chunk in anchors
        if any(token in chunk.text.casefold() for token in ("quyết định", "phê duyệt", "thống nhất", "thông qua"))
    ]
    if decision_chunks:
        templates.append(
            (
                "Nội dung nào là bắt buộc phải quyết định hoặc thống nhất trong cuộc họp?",
                "Tách phần cần ra quyết định khỏi phần chỉ để tham khảo.",
                [decision_chunks[0].chunk_id],
            )
        )
    responsibility_chunks = [
        chunk
        for chunk in anchors
        if any(token in chunk.text.casefold() for token in ("trách nhiệm", "có nghĩa vụ", "chịu trách nhiệm"))
    ]
    if responsibility_chunks:
        templates.append(
            (
                "Cơ quan hoặc đối tượng nào chịu trách nhiệm chính khi áp dụng quy định này?",
                "Làm rõ đầu mối chịu trách nhiệm trước khi giao việc.",
                [responsibility_chunks[0].chunk_id],
            )
        )
    legal_chunks = [
        chunk
        for chunk in anchors
        if any(token in chunk.text.casefold() for token in ("căn cứ", "theo luật", "nghị định", "bộ luật"))
    ]
    if legal_chunks:
        templates.append(
            (
                "Có điểm nào cần bổ sung căn cứ pháp lý hoặc đối chiếu văn bản liên quan không?",
                "Giảm rủi ro thiếu cơ sở khi đưa nội dung vào thực hiện.",
                [legal_chunks[0].chunk_id],
            )
        )
    risk_chunks = [
        chunk
        for chunk in anchors
        if any(token in chunk.text.casefold() for token in ("không được", "cấm", "xử lý", "vi phạm", "rủi ro"))
    ]
    if risk_chunks:
        templates.append(
            (
                "Rủi ro lớn nhất nếu triển khai theo nội dung hiện tại là gì và ai xử lý?",
                "Buộc thảo luận về trách nhiệm, tiến độ và phương án xử lý tình huống.",
                [risk_chunks[0].chunk_id],
            )
        )

    fallback = [
        (
            "Những nhóm đối tượng nào chịu tác động trực tiếp từ nội dung này?",
            "Giúp đánh giá ảnh hưởng thực tế trước khi thông qua hoặc giao nhiệm vụ.",
            citation_pool[:2] or citation_pool,
        ),
        (
            "Các tiêu chí hoặc điều kiện trong tài liệu đã đủ rõ để triển khai chưa?",
            "Làm rõ cách đo lường và tránh hiểu khác nhau giữa các đơn vị.",
            citation_pool[1:3] or citation_pool,
        ),
        (
            "Thời hạn, trình tự hoặc thủ tục nào cần được thống nhất ngay tại cuộc họp?",
            "Tránh chậm tiến độ do chưa chốt mốc thời gian và quy trình.",
            citation_pool[2:4] or citation_pool,
        ),
    ]
    for item in fallback:
        if len(templates) >= minimum:
            break
        templates.append(item)

    questions: list[SuggestedQuestion] = []
    seen_questions: set[str] = set()
    for question, rationale, citation_ids in templates:
        normalized = question.casefold()
        if normalized in seen_questions:
            continue
        ids = [cid for cid in citation_ids if cid] or citation_pool[:1]
        questions.append(
            SuggestedQuestion(
                question=question,
                rationale=rationale,
                citation_ids=ids,
                rubric_score=3,
            )
        )
        seen_questions.add(normalized)
        if len(questions) >= minimum:
            break
    return questions


def _extract_candidate_terms(
    document: NormalizedDocument,
    *,
    existing: set[str],
) -> Iterable[tuple[str, str, list[str]]]:
    pattern = re.compile(r"\b([A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴ][\wÀ-ỹ]{2,}(?:\s+[\wÀ-ỹ]{2,}){0,4})\b")
    counts: dict[str, list[str]] = {}
    for chunk in document.chunks:
        for match in pattern.finditer(chunk.text):
            term = re.sub(r"\s+", " ", match.group(1)).strip()
            key = term.casefold()
            if key in existing or len(term) < 4:
                continue
            counts.setdefault(key, []).append(chunk.chunk_id)

    for key, citation_ids in sorted(counts.items(), key=lambda item: -len(item[1])):
        term = next(
            re.sub(r"\s+", " ", match.group(1)).strip()
            for chunk in document.chunks
            for match in pattern.finditer(chunk.text)
            if match.group(1).casefold() == key
        )
        unique_ids = list(dict.fromkeys(citation_ids))[:3]
        explanation = f"Thuật ngữ/cụm từ quan trọng xuất hiện trong ngữ cảnh tài liệu tại các đoạn được trích dẫn."
        yield term, explanation, unique_ids


def _rank_chunks(chunks: list) -> list:
    keywords = (
        "quy định",
        "trách nhiệm",
        "quyết định",
        "cấm",
        "không được",
        "điều kiện",
        "thời hạn",
        "xử lý",
        "an ninh",
        "hôn nhân",
    )

    def score(chunk) -> int:
        text = chunk.text.casefold()
        return sum(text.count(keyword) for keyword in keywords) + (2 if chunk.article else 0)

    return sorted(chunks, key=score, reverse=True)
