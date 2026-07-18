from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from intelligence import (
    IntelligenceConfigurationError,
    IntelligenceDraft,
    IntelligenceReport,
    NormalizedDocument,
    build_intelligence,
)


ROOT = Path(__file__).resolve().parents[1]


def load_json(name: str) -> dict:
    return json.loads((ROOT / "docs" / "fixtures" / name).read_text(encoding="utf-8"))


def test_handoff_fixtures_match_contract_and_schema() -> None:
    document = NormalizedDocument.model_validate(load_json("normalized_document.mock.json"))
    report = IntelligenceReport.model_validate(load_json("intelligence_report.mock.json"))

    assert document.citation_whitelist == {"P1-D1", "P3-D2", "P5-D3", "P8-D4"}
    assert report.quality.passed is True
    assert "summary" in IntelligenceReport.model_json_schema()["properties"]


def test_document_rejects_duplicate_chunk_ids() -> None:
    payload = load_json("normalized_document.mock.json")
    payload["chunks"].append(payload["chunks"][0].copy())
    with pytest.raises(ValueError, match="unique"):
        NormalizedDocument.model_validate(payload)


def test_map_reduce_filters_unknown_citations_fail_closed() -> None:
    document = NormalizedDocument.model_validate(load_json("normalized_document.mock.json"))
    report_payload = load_json("intelligence_report.mock.json")
    draft_payload = {
        "summary": report_payload["summary"],
        "terms": report_payload["terms"],
        "suggested_questions": report_payload["suggested_questions"],
    }
    draft_payload["summary"]["context"].append(
        {"text": "Nội dung không có trong tài liệu.", "citation_ids": ["P99-FAKE"]}
    )
    calls: list[list[dict[str, str]]] = []

    async def fake_call_llm(messages, response_model):
        calls.append(messages)
        assert response_model is IntelligenceDraft
        return draft_payload

    report = asyncio.run(build_intelligence(document, call_llm=fake_call_llm))

    # Pages 1-7 and page 8 produce two map calls, followed by one reduce call.
    assert len(calls) == 3
    all_ids = {
        citation_id
        for item in report.summary.context
        for citation_id in item.citation_ids
    }
    assert "P99-FAKE" not in all_ids
    assert report.quality.citations_valid is False
    assert report.quality.passed is False
    assert [timing.stage for timing in report.stage_timings] == [
        "map",
        "reduce",
        "validation",
    ]


def test_empty_document_returns_empty_report_without_model_call() -> None:
    payload = load_json("normalized_document.mock.json")
    payload["chunks"] = []
    payload["citations"] = {}
    document = NormalizedDocument.model_validate(payload)
    calls = 0

    async def fake_call_llm(messages, response_model):
        nonlocal calls
        calls += 1
        return {}

    report = asyncio.run(build_intelligence(document, call_llm=fake_call_llm))
    assert calls == 0
    assert report.summary.context == []
    assert report.quality.passed is False


def test_shared_llm_client_is_required() -> None:
    document = NormalizedDocument.model_validate(load_json("normalized_document.mock.json"))
    with pytest.raises(IntelligenceConfigurationError):
        asyncio.run(build_intelligence(document))
