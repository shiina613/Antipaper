import pytest

from src.intelligence.contracts import DocumentChunk, NormalizedDocument
from src.intelligence.terminology import CandidateTerm, _normalize_category, build_terminology_result


@pytest.mark.parametrize(
    ("model_category", "term", "source_text", "expected_category"),
    [
        ("thủ tục hành chính", "Thủ tục hành chính", "Thủ tục hành chính quy định nghĩa vụ.", "procedure_condition"),
        ("nghĩa vụ của người sử dụng lao động", "Nghĩa vụ báo cáo", "Nghĩa vụ báo cáo của đơn vị.", "right_obligation"),
        ("xử phạt vi phạm", "Xử phạt vi phạm", "Xử phạt vi phạm theo quy định.", "sanction_dispute"),
        ("cơ quan có thẩm quyền", "Cơ quan có thẩm quyền", "Cơ quan có thẩm quyền thực hiện nhiệm vụ.", "legal_subject"),
        ("nhãn do provider tự đặt", "Hợp đồng điện tử", "Hợp đồng điện tử được áp dụng.", "technical_concept"),
    ],
)
def test_localized_or_unknown_term_category_never_breaks_report(
    model_category: str,
    term: str,
    source_text: str,
    expected_category: str,
) -> None:
    document = NormalizedDocument(
        document_id="terms",
        file_name="terms.pdf",
        page_count=1,
        chunks=[
            DocumentChunk(
                chunk_id="P1-D1",
                page=1,
                text=source_text,
            )
        ],
    )
    result = build_terminology_result(
        document,
        [
            CandidateTerm(
                term=term,
                category=model_category,
                selection_reason="Thuật ngữ có ý nghĩa pháp lý trong đoạn nguồn.",
                legal_salience=90,
                reader_difficulty=70,
                citation_ids=["P1-D1"],
                explanation="Trình tự thực hiện công việc theo quy định.",
            )
        ],
        implicit_analysis_available=True,
    )

    assert _normalize_category(model_category, term, source_text) == expected_category
    assert result.terms[0].category in {
        "defined_term",
        "legal_subject",
        "right_obligation",
        "procedure_condition",
        "sanction_dispute",
        "technical_concept",
    }
