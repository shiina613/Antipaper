"""Table detection and table-to-markdown helpers.

This module owns the computer-vision side of the pipeline:
1. Load a YOLOv8 table detector.
2. Detect table bounding boxes on page images.
3. Crop detected regions.
4. Convert cropped table images to markdown.

The markdown conversion is intentionally mocked for the MVP scaffold.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Sequence

import cv2
import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from ultralytics import YOLO

    from .paddle_ocr import TableData


BoundingBox = tuple[float, float, float, float]
ImageLike = np.ndarray | Image.Image


@dataclass(frozen=True)
class DetectedTable:
    """A detected table and its position on the source page image."""

    bbox: BoundingBox
    confidence: float | None = None
    class_id: int | None = None


class TableDetector:
    """Detect tables in PDF page images using YOLOv8."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        confidence_threshold: float = 0.25,
    ) -> None:
        self.model_path = Path(model_path) if model_path else None
        self.confidence_threshold = confidence_threshold
        self.model: YOLO | None = None

    def load_model(self) -> YOLO:
        """Load YOLOv8 weights.

        If no custom model path is supplied, this uses the lightweight
        pretrained YOLOv8 nano weights. Replace `model_path` with trained
        table-detection weights once available.
        """

        weights = str(self.model_path) if self.model_path else "yolov8n.pt"
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "ultralytics is required only when YOLO table detection is enabled."
            ) from exc

        self.model = YOLO(weights)
        return self.model

    def detect_tables(self, image: ImageLike) -> list[BoundingBox]:
        """Return detected table bounding boxes as `[x0, y0, x1, y1]`.

        Coordinates are in the pixel coordinate space of the provided image.
        """

        return [table.bbox for table in self.detect(image)]

    def detect(self, image: ImageLike) -> list[DetectedTable]:
        """Return rich table detections including confidence and class id."""

        if self.model is None:
            self.load_model()

        image_array = self._to_numpy(image)
        assert self.model is not None
        results = self.model.predict(
            source=image_array,
            conf=self.confidence_threshold,
            verbose=False,
        )

        detections: list[DetectedTable] = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue

            for box in boxes:
                xyxy = box.xyxy[0].tolist()
                detections.append(
                    DetectedTable(
                        bbox=self._normalize_bbox(xyxy),
                        confidence=float(box.conf[0]) if box.conf is not None else None,
                        class_id=int(box.cls[0]) if box.cls is not None else None,
                    )
                )

        return detections

    def crop_tables(
        self,
        image: ImageLike,
        bounding_boxes: Iterable[Sequence[float]],
    ) -> list[np.ndarray]:
        """Crop table regions from an image using pixel-space bounding boxes."""

        image_array = self._to_numpy(image)
        height, width = image_array.shape[:2]
        crops: list[np.ndarray] = []

        for bbox in bounding_boxes:
            x0, y0, x1, y1 = self._clip_bbox(bbox, width=width, height=height)
            if x1 <= x0 or y1 <= y0:
                continue
            crops.append(image_array[y0:y1, x0:x1].copy())

        return crops

    def table_to_markdown(self, cropped_image: ImageLike) -> str:
        """Convert a cropped table image into markdown.

        This is a placeholder for a future table-structure recognition model or
        LLM-based parser.
        """

        _ = cropped_image
        return (
            "| Column 1 | Column 2 |\n"
            "| --- | --- |\n"
            "| Placeholder | Table content pending parser implementation |"
        )

    @staticmethod
    def _to_numpy(image: ImageLike) -> np.ndarray:
        """Convert PIL or NumPy image input to an OpenCV-friendly array."""

        if isinstance(image, Image.Image):
            return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        return image

    @staticmethod
    def _normalize_bbox(values: Sequence[float]) -> BoundingBox:
        if len(values) != 4:
            raise ValueError(f"Expected 4 bbox values, received {len(values)}.")

        x0, y0, x1, y1 = (float(value) for value in values)
        return (x0, y0, x1, y1)

    @classmethod
    def _clip_bbox(
        cls,
        values: Sequence[float],
        *,
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = cls._normalize_bbox(values)
        left = max(0, min(width, int(round(x0))))
        top = max(0, min(height, int(round(y0))))
        right = max(0, min(width, int(round(x1))))
        bottom = max(0, min(height, int(round(y1))))
        return left, top, right, bottom


def ocr_page(image_bytes: bytes) -> str:
    """Compatibility entry point for the standalone PaddleOCR adapter."""

    from .paddle_ocr import ocr_page as recognize_page

    return recognize_page(image_bytes)


def ocr_table(
    image_bytes: bytes,
    *,
    page: int | None = None,
    bbox: BoundingBox | None = None,
) -> "TableData":
    """Compatibility entry point returning structured PP-StructureV3 output."""

    from .paddle_ocr import ocr_table as recognize_table

    return recognize_table(image_bytes, page=page, bbox=bbox)
