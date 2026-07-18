from __future__ import annotations

import json
from pathlib import Path

from backend.intelligence import NormalizedDocument
from backend.retrieval import render_citations, validate_citations


def document():
    path = Path(__file__).parents[1] / "docs" / "fixtures" / "normalized_document.mock.json"
    return NormalizedDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_valid_citation_uses_authoritative_metadata():
    result = validate_citations(["P3-D2"], document(), ["P3-D2"])
    assert result.valid
    assert result.citations[0].excerpt.startswith("Kinh phí")
    assert render_citations(result)[0]["page"] == 3


def test_blank_duplicate_unknown_and_not_retrieved_are_rejected():
    result = validate_citations(["", "P3-D2", "P3-D2", "P99", "P1-D1"], document(), ["P3-D2"])
    assert not result.valid
    assert len(result.citations) == 1
    assert any("duplicate" in reason for reason in result.invalid_reasons)
    assert any("unknown" in reason for reason in result.invalid_reasons)
    assert any("not retrieved" in reason for reason in result.invalid_reasons)


def test_missing_citation_metadata_falls_back_to_chunk():
    payload = json.loads((Path(__file__).parents[1] / "docs/fixtures/normalized_document.mock.json").read_text(encoding="utf-8"))
    payload["citations"] = {}
    result = validate_citations(["P1-D1"], NormalizedDocument.model_validate(payload))
    assert result.valid
    assert result.citations[0].excerpt.startswith("Cuộc họp")


def test_authoritative_excerpt_must_come_from_referenced_chunk():
    payload = json.loads((Path(__file__).parents[1] / "docs/fixtures/normalized_document.mock.json").read_text(encoding="utf-8"))
    payload["citations"]["P3-D2"]["excerpt"] = "Nội dung bịa đặt"
    result = validate_citations(["P3-D2"], NormalizedDocument.model_validate(payload))
    assert not result.valid
    assert "excerpt" in result.invalid_reasons[0]


def test_terminal_ellipsis_accepts_mid_word_source_prefix_but_rejects_unrelated():
    payload = json.loads((Path(__file__).parents[1] / "docs/fixtures/normalized_document.mock.json").read_text(encoding="utf-8"))
    payload["citations"]["P3-D2"]["excerpt"] = "Kinh phí thực hiện lấy từ ngân s..."
    valid = validate_citations(["P3-D2"], NormalizedDocument.model_validate(payload))
    assert valid.valid

    payload["citations"]["P3-D2"]["excerpt"] = "Kinh phí hoàn toàn khác..."
    invalid = validate_citations(["P3-D2"], NormalizedDocument.model_validate(payload))
    assert not invalid.valid
