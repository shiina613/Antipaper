"""Deterministic evaluation for retrieval and grounded-answer golden cases."""
from __future__ import annotations

import asyncio
import json
import time
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .index import RetrievalIndex
from .qa import GroundedAnswer, GroundedQAService


@dataclass(frozen=True)
class GoldenCase:
    id: str
    question: str
    scope: str
    expected_answer_points: tuple[str, ...]
    gold_citation_ids: tuple[str, ...]
    expected_out_of_scope: bool
    expected_output: str = ""
    category: str = "general"
    difficulty: str = "medium"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GoldenCase":
        return cls(
            id=value["id"], question=value["question"], scope=value["scope"],
            expected_answer_points=tuple(value["expected_answer_points"]),
            gold_citation_ids=tuple(value["gold_citation_ids"]),
            expected_out_of_scope=bool(value["expected_out_of_scope"]),
            expected_output=str(value.get("expected_output", "")),
            category=str(value.get("category", "general")),
            difficulty=str(value.get("difficulty", "medium")),
        )


@dataclass(frozen=True)
class CaseEvaluation:
    case_id: str
    retrieved_ids: tuple[str, ...]
    citation_ids: tuple[str, ...]
    recall_at_5: float
    citation_precision: float
    groundedness: float
    out_of_scope_correct: bool
    latency_ms: float
    answer: str


@dataclass(frozen=True)
class GoldenEvaluation:
    cases: tuple[CaseEvaluation, ...]
    recall_at_5: float
    citation_precision: float
    groundedness: float
    oos_accuracy: float
    latency_ms: float

    @property
    def out_of_scope_accuracy(self) -> float:
        return self.oos_accuracy

    def as_dict(self) -> dict[str, Any]:
        return {
            "recall_at_5": self.recall_at_5,
            "citation_precision": self.citation_precision,
            "groundedness": self.groundedness,
            "oos_accuracy": self.oos_accuracy,
            "latency_ms": self.latency_ms,
            "cases": [case.__dict__ for case in self.cases],
        }


def load_golden_cases(path: str | Path) -> list[GoldenCase]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix.casefold() == ".jsonl":
        payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
    if isinstance(payload, dict):
        payload = payload.get("records", [])
    return [
        GoldenCase.from_dict(item)
        for item in payload
        if item.get("record_type", "qa") == "qa"
    ]


async def evaluate_case(index: RetrievalIndex, case: GoldenCase) -> CaseEvaluation:
    started = time.perf_counter()
    result: GroundedAnswer = await GroundedQAService(index).answer(case.question, top_k=5)
    answer = result.answer.casefold()
    points_hit = all(point.casefold() in answer for point in case.expected_answer_points)
    citation_ids = tuple(result.citation_ids)
    relevant_citations = sum(cid in case.gold_citation_ids for cid in citation_ids)
    citation_precision = relevant_citations / len(citation_ids) if citation_ids else (1.0 if case.expected_out_of_scope else 0.0)
    groundedness = float(points_hit and set(case.gold_citation_ids).issubset(set(citation_ids))) if not case.expected_out_of_scope else float(result.out_of_scope)
    return CaseEvaluation(
        case.id, result.retrieved_ids, citation_ids,
        (len(set(case.gold_citation_ids) & set(result.retrieved_ids)) / len(case.gold_citation_ids)) if case.gold_citation_ids else 0.0,
        citation_precision, groundedness, result.out_of_scope == case.expected_out_of_scope,
        (time.perf_counter() - started) * 1000, result.answer,
    )


async def evaluate_golden_set_async(index: RetrievalIndex, cases: Iterable[GoldenCase]) -> GoldenEvaluation:
    ordered_cases = tuple(cases)
    evaluations = tuple([await evaluate_case(index, case) for case in ordered_cases])
    in_scope = tuple(item for item, case in zip(evaluations, ordered_cases) if case.scope == "in")
    out_scope = tuple(item for item, case in zip(evaluations, ordered_cases) if case.scope == "out")
    count = len(in_scope) or 1
    out_count = len(out_scope) or 1
    return GoldenEvaluation(
        evaluations,
        sum(item.recall_at_5 for item in in_scope) / count,
        sum(item.citation_precision for item in in_scope) / count,
        sum(item.groundedness for item in in_scope) / count,
        sum(item.out_of_scope_correct for item in out_scope) / out_count,
        sum(item.latency_ms for item in evaluations) / (len(evaluations) or 1),
    )


def evaluate_golden_set(index: RetrievalIndex, cases: Iterable[GoldenCase]) -> GoldenEvaluation:
    """Synchronous wrapper; use ``evaluate_golden_set_async`` in async code."""
    coroutine = evaluate_golden_set_async(index, cases)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    result: list[GoldenEvaluation] = []
    failure: list[BaseException] = []
    def run() -> None:
        try:
            result.append(asyncio.run(coroutine))
        except BaseException as exc:
            failure.append(exc)
    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    if failure:
        raise failure[0]
    return result[0]
