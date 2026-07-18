"""YOLOv8 table-region detection helpers.

YOLOv8 is used only for object detection and cropping.  It does not recognize
text, rows, columns, or Markdown; consumers must treat its output as detection
metadata rather than OCR output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO


BoundingBox = tuple[float, float, float, float]
ImageLike = np.ndarray | Image.Image


@dataclass(frozen=True)
class DetectedTable:
    """A detected table and its position on the source page image."""

    bbox: BoundingBox
    confidence: float | None = None
    class_id: int | None = None


class YoloModelConfigurationError(RuntimeError):
    """Raised when table-specific YOLO weights are not configured."""


class TableDetector:
    """Detect tables in PDF page images using YOLOv8."""

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.25,
        device: str | int | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.model: YOLO | None = None

    def load_model(self) -> YOLO:
        """Load YOLOv8 weights.

        A table-specific checkpoint is mandatory. Falling back to generic COCO
        weights would silently produce semantically invalid table detections.
        """

        if not self.model_path.is_file():
            raise YoloModelConfigurationError(
                f"Table-specific YOLO weights not found: {self.model_path}"
            )
        self.model = YOLO(str(self.model_path))
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
        predict_kwargs: dict[str, object] = {
            "source": image_array,
            "conf": self.confidence_threshold,
            "verbose": False,
        }
        if self.device is not None:
            predict_kwargs["device"] = self.device
        results = self.model.predict(
            **predict_kwargs,
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
