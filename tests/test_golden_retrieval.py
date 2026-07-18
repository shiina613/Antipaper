from __future__ import annotations

import json
from pathlib import Path

from backend.intelligence import NormalizedDocument
from backend.retrieval import build_index, evaluate_golden_set, load_golden_cases


ROOT = Path(__file__).parents[1]


def test_golden_metrics_are_grounded_and_repeatable():
    payload = json.loads((ROOT / "docs/fixtures/normalized_document.mock.json").read_text(encoding="utf-8"))
    payload["page_count"] = 10
    payload["chunks"].extend([
        {"chunk_id": "P9-D5", "page": 9, "text": "Phụ lục nêu quy trình kiểm tra hồ sơ.", "chapter": "Phụ lục", "article": None, "clause": None},
        {"chunk_id": "P10-D6", "page": 10, "text": "Biên bản ghi nhận kết quả thực hiện.", "chapter": "Phụ lục", "article": None, "clause": None},
    ])
    payload["citations"].update({
        "P9-D5": {"page": 9, "chapter": "Phụ lục", "article": None, "clause": None, "excerpt": "Phụ lục nêu quy trình kiểm tra hồ sơ."},
        "P10-D6": {"page": 10, "chapter": "Phụ lục", "article": None, "clause": None, "excerpt": "Biên bản ghi nhận kết quả thực hiện."},
    })
    document = NormalizedDocument.model_validate(payload)
    cases = load_golden_cases(ROOT / "tests/fixtures/golden_retrieval.json")
    assert len(cases) == 15
    assert len(document.chunks) > 5
    first = evaluate_golden_set(build_index(document), cases)
    second = evaluate_golden_set(build_index(document), cases)
    assert first.recall_at_5 == 10 / 10
    assert first.citation_precision == 1.0
    assert first.groundedness == 1.0
    assert first.oos_accuracy == 1.0
    assert [(item.retrieved_ids, item.citation_ids, item.groundedness) for item in first.cases] == [(item.retrieved_ids, item.citation_ids, item.groundedness) for item in second.cases]
    assert first.latency_ms >= 0
    by_id = {item.case_id: item for item in first.cases}
    assert set(by_id["in-11"].citation_ids) == {"P3-D2", "P5-D3"}
    assert set(by_id["in-12"].citation_ids) == {"P1-D1", "P8-D4"}
