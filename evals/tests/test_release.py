"""Manual/nightly DeepEval release suite; not collected by normal pytest."""

from __future__ import annotations

import json
import os
from pathlib import Path

from deepeval import assert_test
from deepeval.metrics import SummarizationMetric
from deepeval.models import GPTModel
from deepeval.test_case import LLMTestCase
import pytest

from evals.adapters import BenchmarkApplication
from evals.dataset import ReleaseRecord, load_release_records
from evals.metrics import RefusalMetric, answerable_qa_metrics, meeting_quality_metric


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "evals" / "datasets" / "demo_v1.jsonl"
RECORDS = load_release_records(DATASET_PATH)
QA_RECORDS = [record for record in RECORDS if record.record_type == "qa"]


@pytest.fixture(scope="session")
def judge_model() -> GPTModel:
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for the DeepEval release gate")
    return GPTModel(
        model=os.getenv("EVAL_JUDGE_MODEL", "gpt-5.4"),
        api_key=os.environ["OPENAI_API_KEY"],
        temperature=0,
    )


@pytest.fixture(scope="session")
def application() -> BenchmarkApplication:
    configured = os.getenv("DEMO_DOCUMENT_PATH", "").strip()
    path = Path(configured) if configured else ROOT / RECORDS[0].document_path
    return BenchmarkApplication.from_path(path, use_configured_llm=True)


@pytest.fixture(scope="session")
def report(application: BenchmarkApplication):  # noqa: ANN201
    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_MODEL"):
        pytest.skip("LLM_API_KEY and LLM_MODEL are required for report evaluation")
    result = application.generate_report()
    assert result.report.generation_mode == "llm", "heuristic fallback cannot pass release"
    return result.report


def test_deterministic_refusal_contract(application: BenchmarkApplication) -> None:
    """Keep the CLI suite useful offline while judge-backed tests remain skipped."""
    for record in (item for item in QA_RECORDS if item.scope == "out"):
        assert record.question is not None
        trace = application.answer(record.question)
        assert_test(
            LLMTestCase(input=record.question, actual_output=trace.response.answer),
            [
                RefusalMetric(
                    insufficient_evidence=trace.response.insufficient_evidence,
                    citation_ids=trace.response.citation_ids,
                )
            ],
        )


@pytest.mark.parametrize("record", QA_RECORDS, ids=lambda record: record.id)
def test_grounded_qa_release(
    record: ReleaseRecord,
    application: BenchmarkApplication,
    judge_model: str,
) -> None:
    assert record.question is not None
    trace = application.answer(record.question)
    test_case = LLMTestCase(
        input=record.question,
        actual_output=trace.response.answer,
        expected_output=record.expected_output,
        retrieval_context=list(trace.retrieval_context),
    )
    if record.scope == "out":
        metrics = [
            RefusalMetric(
                insufficient_evidence=trace.response.insufficient_evidence,
                citation_ids=trace.response.citation_ids,
            )
        ]
    else:
        metrics = answerable_qa_metrics(
            judge_model=judge_model,
            actual_citation_ids=trace.response.citation_ids,
            accepted_citation_ids=record.gold_citation_ids,
        )
    assert_test(test_case, metrics)


def test_summary_release(report, application: BenchmarkApplication, judge_model: GPTModel) -> None:  # noqa: ANN001
    summary = report.summary
    actual_output = "\n".join(
        item.text
        for section in (
            summary.context,
            summary.main_content,
            summary.decision_points,
            summary.impact,
        )
        for item in section
    )
    assert_test(
        LLMTestCase(input=application.document.model_dump_json(), actual_output=actual_output),
        [
            SummarizationMetric(
                threshold=0.80,
                model=judge_model,
                assessment_questions=[
                    "Bản tóm tắt có nêu phạm vi và đối tượng áp dụng của Luật không?",
                    "Bản tóm tắt có nêu trách nhiệm của cơ quan và chủ quản hệ thống không?",
                    "Bản tóm tắt có đề cập bảo vệ hệ thống quan trọng và an ninh dữ liệu không?",
                    "Bản tóm tắt có nêu tác động hoặc nghĩa vụ chuyển tiếp không?",
                ],
            )
        ],
    )


def test_terms_release(report, judge_model: GPTModel) -> None:  # noqa: ANN001
    expected = [
        record.model_dump(include={"term", "expected_output"})
        for record in RECORDS
        if record.record_type == "term"
    ]
    actual = [item.model_dump() for item in report.terms]
    assert len(actual) >= 10
    actual_by_term = {
        str(item.get("term", "")).casefold(): item
        for item in actual
    }
    for expected_item in expected[:10]:
        term = str(expected_item.get("term", ""))
        assert_test(
            LLMTestCase(
                input=f"Giải thích thuật ngữ {term} theo ngữ cảnh tài liệu.",
                actual_output=json.dumps(
                    actual_by_term.get(term.casefold(), {}),
                    ensure_ascii=False,
                ),
                expected_output=json.dumps(expected_item, ensure_ascii=False),
            ),
            [
                meeting_quality_metric(
                    name=f"Term quality: {term}",
                    judge_model=judge_model,
                    threshold=0.75,
                )
            ],
        )
    assert_test(
        LLMTestCase(
            input="Giải thích thuật ngữ theo ngữ cảnh tài liệu.",
            actual_output=json.dumps(actual, ensure_ascii=False),
            expected_output=json.dumps(expected, ensure_ascii=False),
        ),
        [meeting_quality_metric(name="Vietnamese contextual terminology", judge_model=judge_model, threshold=0.80)],
    )


def test_suggested_questions_release(report, judge_model: GPTModel) -> None:  # noqa: ANN001
    expected = [
        record.expected_output
        for record in RECORDS
        if record.record_type == "suggested_question"
    ]
    actual = [item.model_dump() for item in report.suggested_questions]
    assert len(actual) >= 5
    normalized_questions = {
        str(item.get("question", "")).casefold().strip()
        for item in actual[:5]
    }
    assert len(normalized_questions) == 5
    for index, item in enumerate(actual[:5], start=1):
        assert_test(
            LLMTestCase(
                input="Sinh câu hỏi phản biện cụ thể, hữu ích cho cuộc họp.",
                actual_output=json.dumps(item, ensure_ascii=False),
                expected_output=json.dumps(expected, ensure_ascii=False),
            ),
            [
                meeting_quality_metric(
                    name=f"Meeting question rubric: {index}",
                    judge_model=judge_model,
                    threshold=0.75,
                )
            ],
        )
    assert_test(
        LLMTestCase(
            input="Sinh câu hỏi phản biện dùng trong cuộc họp.",
            actual_output=json.dumps(actual, ensure_ascii=False),
            expected_output=json.dumps(expected, ensure_ascii=False),
        ),
        [meeting_quality_metric(name="Meeting question quality", judge_model=judge_model, threshold=0.75)],
    )
