"""Run three isolated cold document-processing measurements."""

from __future__ import annotations

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("document", type=Path)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        print(f"{one_run(args.document):.3f}")
        return
    durations = []
    for _ in range(3):
        completed = subprocess.run(
            [sys.executable, __file__, str(args.document.resolve()), "--once"],
            check=True, capture_output=True, text=True,
        )
        durations.append(float(completed.stdout.strip().splitlines()[-1]))
    print("cold runs:", ", ".join(f"{duration:.3f}s" for duration in durations))
    if max(durations) >= 50:
        raise SystemExit("cold-run SLA failed: one run reached 50 seconds")


if __name__ == "__main__":
    main()
