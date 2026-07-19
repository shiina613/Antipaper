"""Run three isolated cold document-processing measurements."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def one_run(path: Path) -> float:
    from src.services.orchestrator import DocumentOrchestrator

    started = time.perf_counter()
    result = DocumentOrchestrator().process(
        document_id="benchmark", file_name=path.name, file_bytes=path.read_bytes()
    )
    assert result.report.page_count > 0
    return time.perf_counter() - started


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile, deliberately dependency-free for release checks."""

    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("document", type=Path, nargs="?")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        if args.document is None:
            parser.error("document is required with --once")
        print(f"{one_run(args.document):.3f}")
        return
    documents = [args.document] if args.document else sorted(args.corpus.glob("*.pdf"))
    if not documents:
        parser.error("no PDF documents found for benchmark")
    if args.runs < 1:
        parser.error("--runs must be positive")

    durations: list[float] = []
    for document in documents:
        document_durations = []
        for _ in range(args.runs):
            completed = subprocess.run(
                [sys.executable, __file__, str(document.resolve()), "--once"],
                check=True, capture_output=True, text=True,
            )
            duration = float(completed.stdout.strip().splitlines()[-1])
            durations.append(duration)
            document_durations.append(duration)
        print(f"{document.name}:", ", ".join(f"{duration:.3f}s" for duration in document_durations))

    p50, p95 = percentile(durations, 0.50), percentile(durations, 0.95)
    print(f"cold corpus p50={p50:.3f}s p95={p95:.3f}s samples={len(durations)}")
    if p50 >= 60 or p95 >= 120:
        raise SystemExit("cold-run SLA failed: require p50 < 60s and p95 < 120s")


if __name__ == "__main__":
    main()
