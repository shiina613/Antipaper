"""End-to-end PDF processing orchestration for the MVP pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Sequence

import fitz
from PIL import Image

from .pdf_parser import DocumentParser, ParsedPage
from .stitcher import DocumentStitcher, StitchedPage, TableMarkdown
from .table_ocr import BoundingBox, DetectedTable, TableDetector


@dataclass(frozen=True)
class ProcessedTable:
    """A detected table with markdown and page-level metadata."""

    page_number: int
    image_bbox: BoundingBox
    page_bbox: BoundingBox
    markdown: str
    confidence: float | None = None


@dataclass(frozen=True)
class ProcessedDocument:
    """Output of the extraction pipeline, ready for AI analysis."""

    source_path: Path
    page_count: int
    parsed_pages: list[ParsedPage]
    stitched_pages: list[StitchedPage]
    tables_by_page: dict[int, list[ProcessedTable]] = field(default_factory=dict)
    processing_seconds: float = 0.0

    @property
    def full_text(self) -> str:
        return "\n\n".join(
            f"[Trang {page.page_number}]\n{page.content}"
            for page in self.stitched_pages
            if page.content
        )


class PdfProcessingPipeline:
    """Run PDF rendering, table detection, text masking, and stitching."""

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.25,
        render_scale: float = 2.0,
    ) -> None:
        self.model_path = Path(model_path)
        self.render_scale = render_scale
        self.detector = TableDetector(
            model_path=self.model_path,
            confidence_threshold=confidence_threshold,
        )
        self.stitcher = DocumentStitcher()

    def process(
        self,
        pdf_path: str | Path,
        max_pages: int | None = None,
    ) -> ProcessedDocument:
        """Process a PDF into stitched page text and table metadata."""

        start_time = perf_counter()
        source_path = Path(pdf_path)
        if not source_path.exists():
            raise FileNotFoundError(f"PDF not found: {source_path}")

        parser = DocumentParser(source_path)
        parsed_pages: list[ParsedPage] = []
        stitched_pages: list[StitchedPage] = []
        tables_by_page: dict[int, list[ProcessedTable]] = {}

        with fitz.open(source_path) as document:
            total_pages = document.page_count
            page_limit = min(max_pages or total_pages, total_pages)

            for page_index in range(page_limit):
                page = document[page_index]
                page_number = page_index + 1
                image = self._render_page(page)
                detections = self.detector.detect(image)
                image_bboxes = [detection.bbox for detection in detections]

                parsed_page = parser.extract_page_text_outside_tables(
                    page=page,
                    page_number=page_number,
                    table_bboxes=image_bboxes,
                    image_size=image.size,
                )
                parsed_pages.append(parsed_page)

                page_tables = self._build_page_tables(
                    page=page,
                    image=image,
                    image_size=image.size,
                    detections=detections,
                )
                tables_by_page[page_number] = page_tables

                markdown_tables = [
                    TableMarkdown(
                        markdown=table.markdown,
                        bbox=table.page_bbox,
                        confidence=table.confidence,
                    )
                    for table in page_tables
                ]
                stitched_pages.append(
                    self.stitcher.stitch_page(parsed_page, markdown_tables)
                )

        elapsed = perf_counter() - start_time
        return ProcessedDocument(
            source_path=source_path,
            page_count=len(stitched_pages),
            parsed_pages=parsed_pages,
            stitched_pages=stitched_pages,
            tables_by_page=tables_by_page,
            processing_seconds=elapsed,
        )

    def _render_page(self, page: fitz.Page) -> Image.Image:
        matrix = fitz.Matrix(self.render_scale, self.render_scale)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

    def _build_page_tables(
        self,
        page: fitz.Page,
        image: Image.Image,
        image_size: tuple[int, int],
        detections: Sequence[DetectedTable],
    ) -> list[ProcessedTable]:
        image_bboxes = [detection.bbox for detection in detections]
        crops = self.detector.crop_tables(image, image_bboxes)
        page_bboxes = [
            self._scale_image_bbox_to_page(bbox, page=page, image_size=image_size)
            for bbox in image_bboxes
        ]

        tables: list[ProcessedTable] = []
        for detection, crop, page_bbox in zip(detections, crops, page_bboxes):
            tables.append(
                ProcessedTable(
                    page_number=page.number + 1,
                    image_bbox=detection.bbox,
                    page_bbox=page_bbox,
                    markdown=self.detector.table_to_markdown(crop),
                    confidence=detection.confidence,
                )
            )
        return tables

    @staticmethod
    def _scale_image_bbox_to_page(
        bbox: BoundingBox,
        *,
        page: fitz.Page,
        image_size: tuple[int, int],
    ) -> BoundingBox:
        image_width, image_height = image_size
        page_width = float(page.rect.width)
        page_height = float(page.rect.height)
        scale_x = page_width / image_width
        scale_y = page_height / image_height
        x0, y0, x1, y1 = bbox
        return (
            float(x0) * scale_x,
            float(y0) * scale_y,
            float(x1) * scale_x,
            float(y1) * scale_y,
        )
