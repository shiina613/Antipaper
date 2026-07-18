from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import pipeline
from pipeline.table_ocr import TableDetector, YoloModelConfigurationError


class FakeBox:
    def __init__(self) -> None:
        self.xyxy = np.array([[10.0, 20.0, 80.0, 70.0]])
        self.conf = np.array([0.91])
        self.cls = np.array([1.0])


class FakeResult:
    boxes = [FakeBox()]


class FakeYolo:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def predict(self, **kwargs: object) -> list[FakeResult]:
        self.kwargs = kwargs
        return [FakeResult()]


def test_yolo_contract_returns_detection_metadata_and_uses_requested_device() -> None:
    detector = TableDetector("unused-in-test.pt", confidence_threshold=0.4, device=0)
    fake_model = FakeYolo()
    detector.model = fake_model  # dependency seam: no weight download in unit tests

    detections = detector.detect(np.zeros((100, 120, 3), dtype=np.uint8))

    assert len(detections) == 1
    assert detections[0].bbox == (10.0, 20.0, 80.0, 70.0)
    assert detections[0].confidence == pytest.approx(0.91)
    assert detections[0].class_id == 1
    assert fake_model.kwargs["device"] == 0
    assert fake_model.kwargs["conf"] == 0.4


def test_crop_clips_bbox_to_image_and_discards_empty_regions() -> None:
    detector = TableDetector("unused-in-test.pt")
    image = np.zeros((50, 60, 3), dtype=np.uint8)

    crops = detector.crop_tables(image, [(-5, 10, 80, 40), (10, 10, 10, 20)])

    assert len(crops) == 1
    assert crops[0].shape == (30, 60, 3)


def test_missing_table_weights_fail_closed_without_generic_yolo_fallback(
    tmp_path: Path,
) -> None:
    detector = TableDetector(tmp_path / "missing-table-model.pt")

    with pytest.raises(YoloModelConfigurationError, match="not found"):
        detector.load_model()


def test_pipeline_exports_no_ocr_adapter_or_placeholder_contract() -> None:
    assert "PaddleOcrAdapter" not in pipeline.__all__
    assert "ocr_page" not in pipeline.__all__
    assert "ocr_table" not in pipeline.__all__
    assert not hasattr(TableDetector, "table_to_markdown")
