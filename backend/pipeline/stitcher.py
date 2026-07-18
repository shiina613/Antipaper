"""Stitch native PDF text and markdown tables into page-level output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from .pdf_parser import ExtractedTextBlock, ParsedPage
from .table_ocr import BoundingBox


@dataclass(frozen=True)
class TableMarkdown:
    """Markdown representation of a detected table and its page position."""

    markdown: str
    bbox: BoundingBox
    confidence: float | None = None


@dataclass(frozen=True)
class StitchedPage:
    """Final stitched content for one PDF page."""

    page_number: int
    content: str


@dataclass(frozen=True)
class _PositionedItem:
    kind: Literal["text", "table"]
    content: str
    bbox: BoundingBox
    order_index: int


class DocumentStitcher:
    """Merge page text and markdown tables by vertical document position."""

    def stitch_document(
        self,
        parsed_pages: Sequence[ParsedPage],
        tables_by_page: dict[int, Sequence[TableMarkdown]] | None = None,
    ) -> list[StitchedPage]:
        """Stitch each parsed page with its markdown tables."""

        tables_by_page = tables_by_page or {}
        return [
            self.stitch_page(
                parsed_page=page,
                tables=tables_by_page.get(page.page_number, []),
            )
            for page in parsed_pages
        ]

    def stitch_page(
        self,
        parsed_page: ParsedPage,
        tables: Sequence[TableMarkdown],
    ) -> StitchedPage:
        """Merge native text blocks and markdown tables for one page.

        Items are sorted top-to-bottom, then left-to-right. Because the parser
        already removes table-overlapping native text, table markdown can be
        inserted directly into the resulting content stream.
        """

        positioned_items = self._build_positioned_items(
            text_blocks=parsed_page.text_blocks,
            tables=tables,
        )

        if not positioned_items and parsed_page.text:
            content = parsed_page.text
        else:
            content = "\n\n".join(item.content for item in positioned_items)

        return StitchedPage(
            page_number=parsed_page.page_number,
            content=content.strip(),
        )

    def _build_positioned_items(
        self,
        text_blocks: Sequence[ExtractedTextBlock],
        tables: Sequence[TableMarkdown],
    ) -> list[_PositionedItem]:
        positioned_items: list[_PositionedItem] = []

        for index, block in enumerate(text_blocks):
            positioned_items.append(
                _PositionedItem(
                    kind="text",
                    content=block.text,
                    bbox=block.bbox,
                    order_index=index,
                )
            )

        offset = len(positioned_items)
        for index, table in enumerate(tables):
            positioned_items.append(
                _PositionedItem(
                    kind="table",
                    content=table.markdown.strip(),
                    bbox=table.bbox,
                    order_index=offset + index,
                )
            )

        return sorted(positioned_items, key=self._sort_key)

    @staticmethod
    def _sort_key(item: _PositionedItem) -> tuple[float, float, int]:
        x0, y0, _, _ = item.bbox
        return (float(y0), float(x0), item.order_index)
