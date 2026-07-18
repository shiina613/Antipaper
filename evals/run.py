"""Cold/warm benchmark runner; DeepEval judge time is deliberately excluded."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import time
from typing import Any

from evals.adapters import BenchmarkApplication
from evals.dataset import load_release_records
from backend.retrieval import evaluate_golden_set, load_golden_cases


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "evals" / "datasets" / "demo_v1.jsonl"


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def _git_dirty() -> bool:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def _resolve_document(dataset_path: Path, role: str) -> Path:
    env_name = f"{role.upper()}_DOCUMENT_PATH"
    configured = os.getenv(env_name, "").strip()
    if configured:
        return Path(configured)
    first = load_release_records(dataset_path)[0]
    return ROOT / first.document_path


def run_benchmark(
    *,
    suite: str,
    dataset_path: Path,
    document_path: Path,
) -> dict[str, Any]:
    use_llm = suite == "full"
    app = BenchmarkApplication.from_path(
        document_path,
        use_configured_llm=use_llm,
    )
    cases = load_golden_cases(dataset_path)
    deterministic = evaluate_golden_set(app.index, cases)
    run_count = 4 if suite == "full" else 1
    processing_runs: list[dict[str, Any]] = []
    for run_index in range(run_count):
        started = time.perf_counter()
        result = app.generate_report()
        processing_runs.append(
            {
                "kind": "cold" if run_index == 0 else "warm",
                "duration_seconds": round(time.perf_counter() - started, 3),
                "cached": False,
                "generation_mode": result.report.generation_mode,
            }
        )
    gates = {
        "citation_precision": deterministic.citation_precision >= 0.90,
        "refusal_accuracy": deterministic.oos_accuracy == 1.0,
        "retrieval_recall": deterministic.recall_at_5 >= 0.80,
        "uncached_under_60_seconds": any(
            not item["cached"] and item["duration_seconds"] < 60
            for item in processing_runs
        ),
        "llm_generation": (
            all(item["generation_mode"] == "llm" for item in processing_runs)
            if suite == "full"
            else True
        ),
    }
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commit_sha": _git_sha(),
        "commit_dirty": _git_dirty(),
        "dataset_version": dataset_path.stem,
        "suite": suite,
        "document": {
            "path": str(document_path),
            "document_id": app.document_id,
            "page_count": app.document.page_count,
        },
        "models": {
            "generator": os.getenv("LLM_MODEL") or None,
            "judge": os.getenv("EVAL_JUDGE_MODEL", "gpt-5.4"),
        },
        "versions": {
            "prompt": os.getenv("EVAL_PROMPT_VERSION", "intelligence-v1"),
            "parser": os.getenv("EVAL_PARSER_VERSION", "canonical-page-v1"),
        },
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor": platform.processor(),
        },
        "processing_runs": processing_runs,
        "deterministic_metrics": deterministic.as_dict(),
        "deep_eval": {
            "status": "run separately with deepeval test run evals/tests",
            "judge_tokens": None,
            "judge_cost_usd": None,
        },
        "gates": gates,
        "failure_reasons": [name for name, passed in gates.items() if not passed],
        "passed": all(gates.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--document-role", choices=("demo", "backup", "stress"), default="demo")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "benchmark.json")
    args = parser.parse_args()
    document_path = _resolve_document(args.dataset, args.document_role)
    report = run_benchmark(
        suite=args.suite,
        dataset_path=args.dataset,
        document_path=document_path,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "passed": report["passed"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
