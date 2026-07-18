"""Run the Paperless Meetings MVP on a PDF and print demo-ready output."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.intelligence import MeetingIntelligenceEngine
from backend.pipeline.processor import PdfProcessingPipeline


def main() -> None:
    args = parse_args()

    pipeline = PdfProcessingPipeline(
        model_path=args.model,
        confidence_threshold=args.confidence,
        render_scale=args.render_scale,
    )
    document = pipeline.process(args.pdf, max_pages=args.max_pages)
    report = MeetingIntelligenceEngine().build_report(
        document=document,
        sample_question=args.question,
    )

    print_header("PROCESSING")
    print(f"File: {document.source_path}")
    print(f"Pages processed: {document.page_count}")
    print(f"Processing time: {document.processing_seconds:.2f}s")
    print(f"Tables detected: {sum(len(tables) for tables in document.tables_by_page.values())}")
    print(f"Extracted/stiched text chars: {len(document.full_text)}")

    print_header("STRUCTURED SUMMARY")
    print_section("Context", report.summary.context)
    print_section("Main content", report.summary.main_content)
    print_section("Decision points", report.summary.decision_points)
    print_section("Impact", report.summary.impact)
    print_section("Risks / notes", report.summary.risks)

    print_header("TERMINOLOGY HIGHLIGHTS")
    for index, term in enumerate(report.terms[: args.term_limit], start=1):
        pages = ", ".join(f"Trang {page}" for page in term.pages)
        print(f"{index}. {term.term}: {term.explanation} [{pages}]")

    print_header("SUGGESTED QUESTIONS")
    for index, question in enumerate(report.questions, start=1):
        citations = ", ".join(question.citations)
        print(f"{index}. {question.question}")
        print(f"   Lý do: {question.rationale}")
        print(f"   Gợi ý tra cứu: {citations}")

    if report.sample_answer is not None:
        print_header("DOCUMENT-GROUNDED Q&A")
        print(f"Q: {report.sample_answer.question}")
        print(f"A: {report.sample_answer.answer}")
        print(f"Citations: {', '.join(report.sample_answer.citations)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Paperless Meetings MVP demo.")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=PROJECT_ROOT / "data" / "01.pdf",
        help="Path to the input PDF.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=PROJECT_ROOT / "models" / "table_detect_yolov8.pt",
        help="Path to YOLO table detection weights.",
    )
    parser.add_argument(
        "--question",
        default="Tài liệu này yêu cầu người dự họp cần lưu ý những nội dung chính nào?",
        help="Sample Vietnamese question for grounded Q&A.",
    )
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--render-scale", type=float, default=2.0)
    parser.add_argument("--term-limit", type=int, default=10)
    return parser.parse_args()


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_section(title: str, items: list[str]) -> None:
    print(f"\n{title}:")
    for item in items:
        print(f"- {item}")


if __name__ == "__main__":
    main()
