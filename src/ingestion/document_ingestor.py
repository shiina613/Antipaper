"""Deterministic document ingestion into the shared NormalizedDocument contract."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Iterable

import fitz

from backend.intelligence.contracts import Citation, DocumentChunk, NormalizedDocument
from backend.pipeline.processor import PdfProcessingPipeline, ProcessedDocument
from backend.pipeline.stitcher import StitchedPage


MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
DEFAULT_YOLO_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "table_detect_yolov8.pt"


class IngestionError(RuntimeError):
    """Base error for deterministic document ingestion failures."""


class UnsupportedFileError(IngestionError):
    """Raised when the input type is not supported by the MVP."""


class FileTooLargeError(IngestionError):
    """Raised when the input exceeds the API contract size limit."""


@dataclass(frozen=True)
class IngestionOptions:
    """Runtime options for the document ingestor."""

    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES
    use_yolo_tables: bool = False
    require_yolo_weights: bool = False
    yolo_model_path: Path = DEFAULT_YOLO_MODEL_PATH
    yolo_confidence: float = 0.25
    render_scale: float = 2.0
    max_pages: int | None = None


@dataclass
class _SectionState:
    chapter: str | None = None
    section: str | None = None
    article: str | None = None
    clause: str | None = None
    point: str | None = None


@dataclass
class _LogicalUnit:
    page: int
    text_parts: list[str]
    chapter: str | None = None
    section: str | None = None
    article: str | None = None
    clause: str | None = None
    point: str | None = None

    @property
    def text(self) -> str:
        return " ".join(part.strip() for part in self.text_parts if part.strip()).strip()


class DocumentIngestor:
    """Load PDF/DOCX files into `NormalizedDocument`.

    The ingestor is deterministic and does not call any LLM. PDF ingestion keeps
    using the YOLOv8 table path when weights are available, with a native
    PyMuPDF fallback for CI and local machines that have not downloaded weights.
    """

    _chapter_pattern = re.compile(r"^\s*(CHƯƠNG|CHUONG|Chương|Chuong)\s+([IVXLCDM\d]+)\b.*", re.IGNORECASE)
    _section_pattern = re.compile(r"^\s*(MỤC|MUC|Mục|Muc)\s+(\d+[a-zA-Z]?)\b.*", re.IGNORECASE)
    _article_pattern = re.compile(r"^\s*(ĐIỀU|DIEU|Điều|Dieu)\s+(\d+[a-zA-Z]?)\b[.:]?\s*(.*)", re.IGNORECASE)
    _clause_pattern = re.compile(r"^\s*((?:Khoản|Khoan)\s+\d+|\d+\.)\s+.*", re.IGNORECASE)
    _point_pattern = re.compile(r"^\s*([a-zA-ZđĐ])\)\s+.*")

    def __init__(self, options: IngestionOptions | None = None) -> None:
        self.options = options or IngestionOptions()

    def ingest(self, path: str | Path) -> NormalizedDocument:
        source_path = Path(path)
        self._validate_file(source_path)
        suffix = source_path.suffix.lower()

        if suffix == ".pdf":
            pages = self._load_pdf_pages(source_path)
        elif suffix == ".docx":
            pages = self._load_docx_pages(source_path)
        else:
            raise UnsupportedFileError("Chỉ hỗ trợ PDF hoặc DOCX.")

        chunks, citations = self._build_chunks_and_citations(pages)
        return NormalizedDocument(
            document_id=self._document_id(source_path),
            file_name=source_path.name,
            page_count=max((page.page_number for page in pages), default=1),
            chunks=chunks,
            citations=citations,
        )

    def _validate_file(self, path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")
        if path.stat().st_size > self.options.max_file_size_bytes:
            raise FileTooLargeError("File vượt quá giới hạn 25 MB.")
        if path.suffix.lower() not in {".pdf", ".docx"}:
            raise UnsupportedFileError("Chỉ hỗ trợ PDF hoặc DOCX.")

    def _load_pdf_pages(self, path: Path) -> list[StitchedPage]:
        if self.options.use_yolo_tables:
            if self.options.yolo_model_path.exists():
                processed = PdfProcessingPipeline(
                    model_path=self.options.yolo_model_path,
                    confidence_threshold=self.options.yolo_confidence,
                    render_scale=self.options.render_scale,
                ).process(path, max_pages=self.options.max_pages)
                return processed.stitched_pages
            if self.options.require_yolo_weights:
                raise IngestionError(
                    f"YOLOv8 weights not found: {self.options.yolo_model_path}"
                )

        return self._load_pdf_pages_native(path)

    def _load_pdf_pages_native(self, path: Path) -> list[StitchedPage]:
        pages: list[StitchedPage] = []
        with fitz.open(path) as document:
            page_limit = min(self.options.max_pages or document.page_count, document.page_count)
            for page_index in range(page_limit):
                page = document[page_index]
                text = page.get_text("text", sort=True).strip()
                table_markdown = self._extract_native_tables_markdown(page)
                content_parts = [part for part in [text, table_markdown] if part]
                pages.append(
                    StitchedPage(
                        page_number=page_index + 1,
                        content="\n\n".join(content_parts),
                    )
                )
        return pages

    def _extract_native_tables_markdown(self, page: fitz.Page) -> str:
        try:
            tables = page.find_tables().tables
        except Exception:
            return ""

        markdown_tables: list[str] = []
        for table in tables:
            rows = table.extract()
            markdown = self._rows_to_markdown(rows)
            if markdown:
                markdown_tables.append(markdown)
        return "\n\n".join(markdown_tables)

    def _load_docx_pages(self, path: Path) -> list[StitchedPage]:
        try:
            from docx import Document
        except ImportError as exc:
            raise IngestionError("python-docx is required for DOCX ingestion.") from exc

        document = Document(path)
        parts: list[str] = []
        parts.extend(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip())
        for table in document.tables:
            rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
            markdown = self._rows_to_markdown(rows)
            if markdown:
                parts.append(markdown)
        return [StitchedPage(page_number=1, content="\n\n".join(parts))]

    def _build_chunks_and_citations(
        self,
        pages: Iterable[StitchedPage],
    ) -> tuple[list[DocumentChunk], dict[str, Citation]]:
        logical_units = self._build_logical_units(pages)
        chunks: list[DocumentChunk] = []
        citations: dict[str, Citation] = {}
        page_indices: dict[int, int] = {}

        for unit in logical_units:
            text = unit.text
            if not text:
                continue
            page_indices[unit.page] = page_indices.get(unit.page, 0) + 1
            chunk_id = f"P{unit.page}-D{page_indices[unit.page]}"
            excerpt = self._excerpt(text)
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                page=unit.page,
                text=text,
                chapter=unit.chapter,
                section=unit.section,
                article=unit.article,
                clause=unit.clause,
                point=unit.point,
            )
            chunks.append(chunk)
            citations[chunk_id] = Citation(
                page=unit.page,
                chapter=unit.chapter,
                section=unit.section,
                article=unit.article,
                clause=unit.clause,
                point=unit.point,
                excerpt=excerpt,
            )

        return chunks, citations

    def _build_logical_units(self, pages: Iterable[StitchedPage]) -> list[_LogicalUnit]:
        units: list[_LogicalUnit] = []
        state = _SectionState()
        current: _LogicalUnit | None = None

        def flush() -> None:
            nonlocal current
            if current is not None and current.text:
                units.append(current)
            current = None

        for page in pages:
            for paragraph in self._split_content(page.content):
                boundary = self._update_section_state(paragraph, state)
                if current is not None and current.page != page.page_number:
                    flush()
                if boundary:
                    flush()
                if current is None:
                    current = _LogicalUnit(
                        page=page.page_number,
                        text_parts=[],
                        chapter=state.chapter,
                        section=state.section,
                        article=state.article,
                        clause=state.clause,
                        point=state.point,
                    )
                current.text_parts.append(paragraph)

        flush()
        return units

    def _update_section_state(self, text: str, state: _SectionState) -> bool:
        first_line = text.splitlines()[0].strip()
        chapter_match = self._chapter_pattern.match(first_line)
        if chapter_match:
            state.chapter = first_line
            state.section = None
            state.article = None
            state.clause = None
            state.point = None
            return True

        section_match = self._section_pattern.match(first_line)
        if section_match:
            state.section = first_line
            state.article = None
            state.clause = None
            state.point = None
            return True

        article_match = self._article_pattern.match(first_line)
        if article_match:
            state.article = f"Điều {article_match.group(2)}"
            state.clause = None
            state.point = None
            return True

        clause_match = self._clause_pattern.match(first_line)
        if clause_match:
            state.clause = clause_match.group(1).rstrip(".")
            state.point = None
            return True

        point_match = self._point_pattern.match(first_line)
        if point_match:
            state.point = point_match.group(1).lower()
            return True

        return False

    @staticmethod
    def _split_content(content: str) -> list[str]:
        normalized = re.sub(r"\r\n?", "\n", content or "")
        paragraphs = [
            re.sub(r"\s+", " ", paragraph).strip()
            for paragraph in re.split(r"\n{2,}", normalized)
            if paragraph.strip()
        ]
        if len(paragraphs) <= 1:
            paragraphs = [
                re.sub(r"\s+", " ", line).strip()
                for line in normalized.splitlines()
                if line.strip()
            ]
        return [paragraph for paragraph in paragraphs if len(paragraph) >= 3]

    @staticmethod
    def _rows_to_markdown(rows: list[list[str | None]]) -> str:
        clean_rows = [
            [str(cell or "").strip().replace("\n", " ") for cell in row]
            for row in rows
            if any(str(cell or "").strip() for cell in row)
        ]
        if not clean_rows:
            return ""

        column_count = max(len(row) for row in clean_rows)
        padded_rows = [row + [""] * (column_count - len(row)) for row in clean_rows]
        header = padded_rows[0]
        separator = ["---"] * column_count
        body = padded_rows[1:]

        def format_row(row: list[str]) -> str:
            return "| " + " | ".join(row) + " |"

        return "\n".join(
            [format_row(header), format_row(separator), *[format_row(row) for row in body]]
        )

    @staticmethod
    def _excerpt(text: str, max_chars: int = 220) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= max_chars:
            return compact
        prefix = compact[: max_chars - 3].rstrip()
        if " " in prefix:
            prefix = prefix.rsplit(" ", 1)[0]
        return prefix + "..."

    @staticmethod
    def _document_id(path: Path) -> str:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return digest[:16]


def ingest_document(
    path: str | Path,
    options: IngestionOptions | None = None,
) -> NormalizedDocument:
    return DocumentIngestor(options).ingest(path)
