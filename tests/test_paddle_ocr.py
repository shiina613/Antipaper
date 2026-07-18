from __future__ import annotations

import base64

import numpy as np
import pytest

from pipeline.paddle_ocr import (
    InvalidImageError,
    OcrActivationPolicy,
    PaddleOcrAdapter,
)


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class FakeBackend:
    def recognize_page(self, image: np.ndarray):
        assert image.shape[:2] == (1, 1)
        return {"res": {"rec_texts": ["Cộng hòa", "Việt Nam"], "rec_scores": [0.99, 0.98]}}

    def recognize_table(self, image: np.ndarray):
        assert image.shape[:2] == (1, 1)
        return {
            "res": {
                "pred_html": (
                    "<table><tr><th>Cơ quan</th><th>Tiến độ</th></tr>"
                    "<tr><td>Ủy ban</td><td>Quý IV</td></tr></table>"
                ),
                "rec_texts": ["Cơ quan", "Tiến độ", "Ủy ban", "Quý IV"],
                "rec_scores": [0.99, 0.98, 0.97, 0.96],
            }
        }


def test_page_ocr_preserves_vietnamese_text() -> None:
    adapter = PaddleOcrAdapter(FakeBackend())
    assert adapter.ocr_page(PNG_1X1) == "Cộng hòa\nViệt Nam"


def test_table_ocr_preserves_rows_columns_markdown_and_metadata() -> None:
    adapter = PaddleOcrAdapter(FakeBackend())
    table = adapter.ocr_table(
        PNG_1X1,
        page=4,
        bbox=(10.0, 20.0, 300.0, 400.0),
    )

    assert (table.row_count, table.column_count) == (2, 2)
    assert [cell.text for cell in table.cells] == [
        "Cơ quan",
        "Tiến độ",
        "Ủy ban",
        "Quý IV",
    ]
    assert "| Ủy ban | Quý IV |" in table.markdown
    assert table.page == 4
    assert table.bbox == (10.0, 20.0, 300.0, 400.0)
    assert table.confidence == pytest.approx(0.975)
    assert '"row_count":2' in table.to_json(indent=None)


def test_ocr_policy_uses_content_quality_not_filename() -> None:
    policy = OcrActivationPolicy(min_native_chars=20)
    assert policy.should_ocr_page("ít chữ") is True
    assert policy.should_ocr_page("Nội dung native đủ dài và có chất lượng tốt.") is False
    assert policy.should_ocr_table(
        is_image_table=True,
        native_row_count=10,
        native_column_count=10,
        native_text="đã có text",
    ) is True
    assert policy.should_ocr_table(
        is_image_table=False,
        native_row_count=3,
        native_column_count=2,
        native_text="bảng native",
    ) is False


def test_invalid_image_bytes_fail_explicitly() -> None:
    adapter = PaddleOcrAdapter(FakeBackend())
    with pytest.raises(InvalidImageError):
        adapter.ocr_page(b"not-an-image")
