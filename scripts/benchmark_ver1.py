"""Create a reproducible ver1 benchmark for the document ingestion pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter
from typing import Any

import fitz


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from ingestion import IngestionOptions, ingest_document


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf.resolve()
    output_json = args.output.resolve()
    output_md = args.markdown.resolve()
    yolo_model_path = args.yolo_model.resolve()

    if not pdf_path.exists():
        raise FileNotFoundError(f"Benchmark PDF not found: {pdf_path}")

    with fitz.open(pdf_path) as document:
        source_page_count = document.page_count

    options = IngestionOptions(
        use_yolo_tables=args.use_yolo,
        require_yolo_weights=False,
        yolo_model_path=yolo_model_path,
        yolo_confidence=args.yolo_confidence,
        render_scale=args.render_scale,
        max_pages=args.max_pages,
    )

    durations: list[float] = []
    normalized = None
    for _ in range(args.runs):
        started = perf_counter()
        normalized = ingest_document(pdf_path, options)
        durations.append(perf_counter() - started)

    assert normalized is not None
    elapsed = durations[-1]
    chunk_pages = {chunk.page for chunk in normalized.chunks}
    chunk_ids = [chunk.chunk_id for chunk in normalized.chunks]
    citation_keys = set(normalized.citations)
    chunk_id_set = set(chunk_ids)
    character_count = sum(len(chunk.text) for chunk in normalized.chunks)
    article_chunk_count = sum(1 for chunk in normalized.chunks if chunk.article)
    clause_chunk_count = sum(1 for chunk in normalized.chunks if chunk.clause)

    result: dict[str, Any] = {
        "benchmark_id": args.benchmark_id,
        "project": "Antipaper / Paperless Meetings",
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "source": {
            "path": str(pdf_path.relative_to(PROJECT_ROOT)),
            "file_size_bytes": pdf_path.stat().st_size,
            "source_page_count": source_page_count,
        },
        "configuration": {
            "runs": args.runs,
            "max_pages": args.max_pages,
            "use_yolo_tables": options.use_yolo_tables,
            "yolo_model_path": str(yolo_model_path.relative_to(PROJECT_ROOT))
            if yolo_model_path.is_relative_to(PROJECT_ROOT)
            else str(yolo_model_path),
            "yolo_weights_exists": yolo_model_path.exists(),
            "yolo_confidence": args.yolo_confidence,
            "render_scale": args.render_scale,
        },
        "timing": {
            "durations_seconds": durations,
            "last_run_seconds": elapsed,
            "mean_seconds": statistics.fmean(durations),
            "pages_per_second_last_run": normalized.page_count / elapsed if elapsed else None,
        },
        "normalized_document": {
            "document_id": normalized.document_id,
            "file_name": normalized.file_name,
            "page_count": normalized.page_count,
            "chunk_count": len(normalized.chunks),
            "citation_count": len(normalized.citations),
            "character_count": character_count,
            "article_chunk_count": article_chunk_count,
            "clause_chunk_count": clause_chunk_count,
            "pages_with_chunks": sorted(chunk_pages),
        },
        "contract_checks": {
            "chunk_ids_unique": len(chunk_ids) == len(chunk_id_set),
            "citation_keys_match_chunks": citation_keys == chunk_id_set,
            "all_chunk_pages_within_page_count": all(
                1 <= chunk.page <= normalized.page_count for chunk in normalized.chunks
            ),
            "has_page_coverage": len(chunk_pages) == normalized.page_count,
            "has_articles": article_chunk_count > 0,
            "has_clauses": clause_chunk_count > 0,
        },
    }
    result["contract_checks"]["passed"] = all(result["contract_checks"].values())

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(result), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["contract_checks"]["passed"] else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ver1 ingestion benchmark.")
    parser.add_argument("--pdf", type=Path, default=PROJECT_ROOT / "data" / "01.pdf")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "docs" / "benchmarks" / "ver1.json")
    parser.add_argument("--markdown", type=Path, default=PROJECT_ROOT / "docs" / "benchmarks" / "ver1.md")
    parser.add_argument("--yolo-model", type=Path, default=PROJECT_ROOT / "models" / "table_detect_yolov8.pt")
    parser.add_argument("--yolo-confidence", type=float, default=0.25)
    parser.add_argument("--render-scale", type=float, default=2.0)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--use-yolo", action="store_true")
    parser.add_argument("--benchmark-id", default="ver1")
    return parser.parse_args()


def render_markdown(result: dict[str, Any]) -> str:
    checks = result["contract_checks"]
    timing = result["timing"]
    source = result["source"]
    config = result["configuration"]
    normalized = result["normalized_document"]

    lines = [
        f"# Benchmark {result['benchmark_id']}",
        "",
        "## Source",
        "",
        f"- File: `{source['path']}`",
        f"- File size: `{source['file_size_bytes']}` bytes",
        f"- Source pages: `{source['source_page_count']}`",
        "",
        "## Configuration",
        "",
        f"- Runs: `{config['runs']}`",
        f"- Max pages: `{config['max_pages']}`",
        f"- Use YOLO tables: `{config['use_yolo_tables']}`",
        f"- YOLO weights exists: `{config['yolo_weights_exists']}`",
        f"- YOLO model: `{config['yolo_model_path']}`",
        "",
        "## Timing",
        "",
        f"- Last run: `{timing['last_run_seconds']:.3f}s`",
        f"- Mean: `{timing['mean_seconds']:.3f}s`",
        f"- Pages/sec: `{timing['pages_per_second_last_run']:.3f}`",
        "",
        "## Normalized Document",
        "",
        f"- Document ID: `{normalized['document_id']}`",
        f"- Page count: `{normalized['page_count']}`",
        f"- Chunk count: `{normalized['chunk_count']}`",
        f"- Citation count: `{normalized['citation_count']}`",
        f"- Character count: `{normalized['character_count']}`",
        f"- Article chunks: `{normalized['article_chunk_count']}`",
        f"- Clause chunks: `{normalized['clause_chunk_count']}`",
        "",
        "## Contract Checks",
        "",
    ]
    for key, value in checks.items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
