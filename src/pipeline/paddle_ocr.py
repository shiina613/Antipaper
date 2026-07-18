"""Lazy PaddleOCR/PP-StructureV3 adapters for page and table fallbacks.

The routing decision belongs to the ingestion pipeline.  This module accepts
only image bytes plus optional source metadata, making it independently
testable and safe to import when PaddleOCR is not installed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from html.parser import HTMLParser
from io import BytesIO
import json
import re
from statistics import fmean
from typing import Any, Protocol

import numpy as np
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, model_validator

BoundingBox = tuple[float, float, float, float]


class OcrError(RuntimeError):
    """Base exception for OCR initialization and inference failures."""


class InvalidImageError(OcrError):
    """Raised when image bytes are empty or cannot be decoded."""


class OcrDependencyError(OcrError):
    """Raised when the optional PaddleOCR runtime is unavailable."""


class TableCell(BaseModel):
    """One logical table cell, including merged-cell dimensions."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    row: int = Field(ge=0)
    column: int = Field(ge=0)
    text: str = ""
    confidence: float | None = Field(default=None, ge=0, le=1)
    rowspan: int = Field(default=1, ge=1)
    colspan: int = Field(default=1, ge=1)
    bbox: BoundingBox | None = None


class TableData(BaseModel):
    """Structured table output suitable for Markdown and JSON consumers."""

    model_config = ConfigDict(extra="forbid")

    cells: list[TableCell]
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    markdown: str
    page: int | None = Field(default=None, ge=1)
    bbox: BoundingBox | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_cell_bounds(self) -> "TableData":
        for cell in self.cells:
            if cell.row + cell.rowspan > self.row_count:
                raise ValueError("cell row span exceeds row_count")
            if cell.column + cell.colspan > self.column_count:
                raise ValueError("cell column span exceeds column_count")
        return self

    def to_json(self, *, indent: int | None = 2) -> str:
        return self.model_dump_json(indent=indent)


class OcrBackend(Protocol):
    """Backend seam used by production Paddle models and unit-test doubles."""

    def recognize_page(self, image: np.ndarray) -> Any: ...

    def recognize_table(self, image: np.ndarray) -> Any: ...


class OcrActivationPolicy(BaseModel):
    """Content-based fallback thresholds; filenames never affect routing."""

    min_native_chars: int = Field(default=80, ge=0)
    min_alnum_ratio: float = Field(default=0.35, ge=0, le=1)
    min_table_rows: int = Field(default=2, ge=1)
    min_table_columns: int = Field(default=2, ge=1)

    def should_ocr_page(self, native_text: str | None) -> bool:
        compact = re.sub(r"\s+", "", native_text or "")
        if len(compact) < self.min_native_chars:
            return True
        alnum_count = sum(character.isalnum() for character in compact)
        return alnum_count / max(len(compact), 1) < self.min_alnum_ratio

    def should_ocr_table(
        self,
        *,
        is_image_table: bool,
        native_row_count: int = 0,
        native_column_count: int = 0,
        native_text: str | None = None,
    ) -> bool:
        if is_image_table:
            return True
        return (
            native_row_count < self.min_table_rows
            or native_column_count < self.min_table_columns
            or not (native_text or "").strip()
        )


class PaddleOcrBackend:
    """Lazy production backend using PaddleOCR and PP-StructureV3."""

    def __init__(self, *, lang: str = "vi", device: str | None = None) -> None:
        self.lang = lang
        self.device = device
        self._page_model: Any = None
        self._table_model: Any = None

    def recognize_page(self, image: np.ndarray) -> Any:
        if self._page_model is None:
            PaddleOCR, _ = self._load_classes()
            self._page_model = PaddleOCR(
                lang=self.lang,
                device=self._resolve_device(),
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        if hasattr(self._page_model, "predict"):
            return self._page_model.predict(input=image)
        return self._page_model.ocr(image, cls=True)

    def recognize_table(self, image: np.ndarray) -> Any:
        if self._table_model is None:
            _, PPStructureV3 = self._load_classes()
            self._table_model = PPStructureV3(
                lang=self.lang,
                device=self._resolve_device(),
                layout_threshold=0.1,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                use_seal_recognition=False,
                use_table_recognition=True,
                use_formula_recognition=False,
                use_chart_recognition=False,
                use_region_detection=False,
            )
        return self._table_model.predict(
            input=image,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            use_seal_recognition=False,
            use_table_recognition=True,
            use_formula_recognition=False,
            use_chart_recognition=False,
            use_region_detection=False,
            layout_threshold=0.1,
        )

    def _resolve_device(self) -> str:
        if self.device is not None:
            return self.device
        try:
            import paddle
        except (ImportError, ModuleNotFoundError):
            return "cpu"
        if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
            return "gpu:0"
        return "cpu"

    @staticmethod
    def _load_classes() -> tuple[Any, Any]:
        try:
            # On Windows, importing Paddle CUDA before ModelScope's CPU Torch
            # can make torch/lib/shm.dll bind incompatible native symbols.
            # PaddleOCR imports ModelScope indirectly, so establish Torch first.
            import torch  # noqa: F401
            from paddleocr import PaddleOCR, PPStructureV3
        except (ImportError, ModuleNotFoundError) as exc:
            raise OcrDependencyError(
                "PaddleOCR with PP-StructureV3 is required for OCR fallback. "
                "Install the PaddlePaddle runtime appropriate for the machine "
                "and paddleocr>=3.0."
            ) from exc
        return PaddleOCR, PPStructureV3


class PaddleOcrAdapter:
    """Normalize Paddle output into stable text and table contracts."""

    def __init__(self, backend: OcrBackend | None = None) -> None:
        self.backend = backend or PaddleOcrBackend()

    def ocr_page(self, image_bytes: bytes) -> str:
        image = self._decode(image_bytes)
        raw = self.backend.recognize_page(image)
        lines = self._extract_text_lines(raw)
        return "\n".join(text for text, _ in lines if text.strip())

    def ocr_table(
        self,
        image_bytes: bytes,
        *,
        page: int | None = None,
        bbox: BoundingBox | None = None,
    ) -> TableData:
        image = self._decode(image_bytes)
        raw = self.backend.recognize_table(image)
        cells = self._extract_cells(raw)
        if not cells:
            raise OcrError("PP-StructureV3 returned no table cells")
        row_count = max(cell.row + cell.rowspan for cell in cells)
        column_count = max(cell.column + cell.colspan for cell in cells)
        scores = [cell.confidence for cell in cells if cell.confidence is not None]
        return TableData(
            cells=cells,
            row_count=row_count,
            column_count=column_count,
            markdown=self._cells_to_markdown(cells, row_count, column_count),
            page=page,
            bbox=bbox,
            confidence=fmean(scores) if scores else None,
        )

    @staticmethod
    def _decode(image_bytes: bytes) -> np.ndarray:
        if not image_bytes:
            raise InvalidImageError("image_bytes must not be empty")
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                return np.asarray(image.convert("RGB"))
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise InvalidImageError("image_bytes could not be decoded") from exc

    @classmethod
    def _extract_text_lines(cls, raw: Any) -> list[tuple[str, float | None]]:
        plain = cls._to_plain(raw)
        lines: list[tuple[str, float | None]] = []

        def walk(value: Any) -> None:
            if isinstance(value, Mapping):
                texts = value.get("rec_texts") or value.get("texts")
                scores = value.get("rec_scores") or value.get("scores") or []
                if isinstance(texts, Sequence) and not isinstance(texts, (str, bytes)):
                    for index, text in enumerate(texts):
                        score = scores[index] if index < len(scores) else None
                        lines.append((str(text), cls._score(score)))
                    return
                for nested in value.values():
                    walk(nested)
                return
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                # PaddleOCR 2.x shape: [box, (text, confidence)].
                if (
                    len(value) == 2
                    and isinstance(value[1], Sequence)
                    and not isinstance(value[1], (str, bytes))
                    and len(value[1]) >= 2
                    and isinstance(value[1][0], str)
                ):
                    lines.append((value[1][0], cls._score(value[1][1])))
                    return
                for nested in value:
                    walk(nested)

        walk(plain)
        deduplicated: list[tuple[str, float | None]] = []
        seen: set[str] = set()
        for text, score in lines:
            if text not in seen:
                seen.add(text)
                deduplicated.append((text, score))
        return deduplicated

    @classmethod
    def _extract_cells(cls, raw: Any) -> list[TableCell]:
        plain = cls._to_plain(raw)

        for node in cls._walk_mappings(plain):
            normalized_cells = node.get("cells")
            if isinstance(normalized_cells, Sequence) and normalized_cells:
                try:
                    return [TableCell.model_validate(cell) for cell in normalized_cells]
                except (TypeError, ValueError):
                    pass

        for node in cls._walk_mappings(plain):
            html = node.get("pred_html") or node.get("html")
            if isinstance(html, str) and "<tr" in html.lower():
                parser = _TableHtmlParser()
                parser.feed(html)
                if parser.cells:
                    scores = cls._extract_text_lines(node)
                    return cls._attach_scores(parser.cells, scores)

        for node in cls._walk_mappings(plain):
            markdown = node.get("markdown")
            if isinstance(markdown, str):
                cells = cls._markdown_to_cells(markdown)
                if cells:
                    return cells
        return []

    @staticmethod
    def _attach_scores(
        cells: list[TableCell],
        lines: list[tuple[str, float | None]],
    ) -> list[TableCell]:
        score_by_text = {text.strip(): score for text, score in lines if text.strip()}
        return [
            cell.model_copy(update={"confidence": score_by_text.get(cell.text.strip())})
            for cell in cells
        ]

    @staticmethod
    def _cells_to_markdown(
        cells: Sequence[TableCell],
        row_count: int,
        column_count: int,
    ) -> str:
        grid = [["" for _ in range(column_count)] for _ in range(row_count)]
        for cell in cells:
            grid[cell.row][cell.column] = cell.text.replace("|", "\\|").replace("\n", " ")
        if not grid:
            return ""
        lines = ["| " + " | ".join(row) + " |" for row in grid]
        separator = "| " + " | ".join("---" for _ in range(column_count)) + " |"
        lines.insert(1, separator)
        return "\n".join(lines)

    @staticmethod
    def _markdown_to_cells(markdown: str) -> list[TableCell]:
        rows: list[list[str]] = []
        for line in markdown.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            values = [value.strip() for value in stripped.strip("|").split("|")]
            if values and all(re.fullmatch(r":?-{3,}:?", value) for value in values):
                continue
            rows.append(values)
        return [
            TableCell(row=row, column=column, text=text)
            for row, values in enumerate(rows)
            for column, text in enumerate(values)
        ]

    @classmethod
    def _to_plain(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Mapping):
            return {str(key): cls._to_plain(item) for key, item in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [cls._to_plain(item) for item in value]
        json_value = getattr(value, "json", None)
        if callable(json_value):
            json_value = json_value()
        if isinstance(json_value, str):
            try:
                return cls._to_plain(json.loads(json_value))
            except json.JSONDecodeError:
                pass
        if json_value is not None and json_value is not value:
            return cls._to_plain(json_value)
        if hasattr(value, "model_dump"):
            return cls._to_plain(value.model_dump())
        if hasattr(value, "__dict__"):
            return cls._to_plain(vars(value))
        return str(value)

    @staticmethod
    def _walk_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
        if isinstance(value, Mapping):
            yield value
            for nested in value.values():
                yield from PaddleOcrAdapter._walk_mappings(nested)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for nested in value:
                yield from PaddleOcrAdapter._walk_mappings(nested)

    @staticmethod
    def _score(value: Any) -> float | None:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return None
        return min(1.0, max(0.0, score))


class _TableHtmlParser(HTMLParser):
    """Small HTML-table parser that preserves row/column spans."""

    def __init__(self) -> None:
        super().__init__()
        self.cells: list[TableCell] = []
        self._row = -1
        self._column = 0
        self._occupied: set[tuple[int, int]] = set()
        self._current: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            self._row += 1
            self._column = 0
            return
        if tag not in {"td", "th"} or self._row < 0:
            return
        while (self._row, self._column) in self._occupied:
            self._column += 1
        attributes = dict(attrs)
        rowspan = max(1, int(attributes.get("rowspan") or 1))
        colspan = max(1, int(attributes.get("colspan") or 1))
        self._current = {
            "row": self._row,
            "column": self._column,
            "rowspan": rowspan,
            "colspan": colspan,
            "parts": [],
        }
        for row in range(self._row, self._row + rowspan):
            for column in range(self._column, self._column + colspan):
                self._occupied.add((row, column))

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() not in {"td", "th"} or self._current is None:
            return
        text = re.sub(r"\s+", " ", "".join(self._current.pop("parts"))).strip()
        cell = TableCell(text=text, **self._current)
        self.cells.append(cell)
        self._column = cell.column + cell.colspan
        self._current = None


_DEFAULT_ADAPTER: PaddleOcrAdapter | None = None


def _default_adapter() -> PaddleOcrAdapter:
    global _DEFAULT_ADAPTER
    if _DEFAULT_ADAPTER is None:
        _DEFAULT_ADAPTER = PaddleOcrAdapter()
    return _DEFAULT_ADAPTER


def ocr_page(image_bytes: bytes) -> str:
    """OCR a page image while preserving Paddle's Vietnamese Unicode text."""

    return _default_adapter().ocr_page(image_bytes)


def ocr_table(
    image_bytes: bytes,
    *,
    page: int | None = None,
    bbox: BoundingBox | None = None,
) -> TableData:
    """Recognize table structure and return Markdown plus JSON-ready cells."""

    return _default_adapter().ocr_table(image_bytes, page=page, bbox=bbox)
