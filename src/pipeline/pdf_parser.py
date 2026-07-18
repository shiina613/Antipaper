"""Native PDF text extraction with table-region masking."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import fitz

BoundingBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class ExtractedTextBlock:
    """A native text block extracted from a PDF page."""

    text: str
    bbox: BoundingBox
    block_no: int


@dataclass(frozen=True)
class ParsedPage:
    """Text extracted from one page after table regions were masked."""

    page_number: int
    text: str
    text_blocks: list[ExtractedTextBlock] = field(default_factory=list)


class DocumentParser:
    """Extract native PDF text while ignoring detected table areas."""

    def __init__(self, pdf_path: str | Path) -> None:
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")

    def parse(
        self,
        table_bboxes_by_page: dict[int, Sequence[BoundingBox]] | None = None,
        image_sizes_by_page: dict[int, tuple[int, int]] | None = None,
    ) -> list[ParsedPage]:
        """Parse all pages and exclude native text inside table boxes.

        Args:
            table_bboxes_by_page: Mapping of 1-based page number to YOLO table
                boxes. If `image_sizes_by_page` is provided, boxes are treated as
                image pixel coordinates and scaled into PDF page coordinates.
                Otherwise, boxes are assumed to already be in PDF coordinates.
            image_sizes_by_page: Mapping of 1-based page number to `(width,
                height)` for the rendered image passed to YOLO.
        """

        parsed_pages: list[ParsedPage] = []
        table_bboxes_by_page = table_bboxes_by_page or {}
        image_sizes_by_page = image_sizes_by_page or {}

        with fitz.open(self.pdf_path) as document:
            for page_index, page in enumerate(document):
                page_number = page_index + 1
                table_bboxes = table_bboxes_by_page.get(page_number, [])
                image_size = image_sizes_by_page.get(page_number)
                parsed_pages.append(
                    self.extract_page_text_outside_tables(
                        page=page,
                        page_number=page_number,
                        table_bboxes=table_bboxes,
                        image_size=image_size,
                    )
                )

        return parsed_pages

    def extract_page_text_outside_tables(
        self,
        page: fitz.Page,
        page_number: int,
        table_bboxes: Sequence[BoundingBox],
        image_size: tuple[int, int] | None = None,
    ) -> ParsedPage:
        """Extract text blocks whose centers are not inside table regions."""

        page_bboxes = self._scale_bboxes_to_page(
            table_bboxes=table_bboxes,
            page=page,
            image_size=image_size,
        )

        kept_blocks: list[ExtractedTextBlock] = []
        for block in page.get_text("blocks", sort=True):
            x0, y0, x1, y1, text, block_no, *_ = block
            clean_text = str(text).strip()
            if not clean_text:
                continue

            block_bbox = (float(x0), float(y0), float(x1), float(y1))
            if self._is_masked(block_bbox, page_bboxes):
                continue

            kept_blocks.append(
                ExtractedTextBlock(
                    text=clean_text,
                    bbox=block_bbox,
                    block_no=int(block_no),
                )
            )

        page_text = "\n\n".join(block.text for block in kept_blocks)
        return ParsedPage(
            page_number=page_number,
            text=page_text,
            text_blocks=kept_blocks,
        )

    @staticmethod
    def _scale_bboxes_to_page(
        table_bboxes: Sequence[BoundingBox],
        page: fitz.Page,
        image_size: tuple[int, int] | None,
    ) -> list[BoundingBox]:
        """Scale image-space boxes into PyMuPDF page coordinate space."""

        if image_size is None:
            return [tuple(float(value) for value in bbox) for bbox in table_bboxes]

        image_width, image_height = image_size
        if image_width <= 0 or image_height <= 0:
            raise ValueError("Image size must contain positive width and height.")

        page_width = float(page.rect.width)
        page_height = float(page.rect.height)
        scale_x = page_width / image_width
        scale_y = page_height / image_height

        scaled: list[BoundingBox] = []
        for x0, y0, x1, y1 in table_bboxes:
            scaled.append(
                (
                    float(x0) * scale_x,
                    float(y0) * scale_y,
                    float(x1) * scale_x,
                    float(y1) * scale_y,
                )
            )
        return scaled

    @staticmethod
    def _is_masked(
        block_bbox: BoundingBox,
        table_bboxes: Sequence[BoundingBox],
        overlap_threshold: float = 0.35,
    ) -> bool:
        """Return true when a text block meaningfully overlaps a table box."""

        if not table_bboxes:
            return False

        block_area = DocumentParser._area(block_bbox)
        if block_area <= 0:
            return False

        for table_bbox in table_bboxes:
            overlap_area = DocumentParser._intersection_area(block_bbox, table_bbox)
            if overlap_area / block_area >= overlap_threshold:
                return True

        return False

    @staticmethod
    def _area(bbox: BoundingBox) -> float:
        x0, y0, x1, y1 = bbox
        return max(0.0, x1 - x0) * max(0.0, y1 - y0)

    @staticmethod
    def _intersection_area(left: BoundingBox, right: BoundingBox) -> float:
        left_x0, left_y0, left_x1, left_y1 = left
        right_x0, right_y0, right_x1, right_y1 = right

        x_overlap = max(0.0, min(left_x1, right_x1) - max(left_x0, right_x0))
        y_overlap = max(0.0, min(left_y1, right_y1) - max(left_y0, right_y0))
        return x_overlap * y_overlap
