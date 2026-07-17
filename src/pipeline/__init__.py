"""Data extraction pipeline components for Paperless Meetings."""

from .pdf_parser import DocumentParser, ExtractedTextBlock, ParsedPage
from .processor import PdfProcessingPipeline, ProcessedDocument, ProcessedTable
from .stitcher import DocumentStitcher, StitchedPage, TableMarkdown
from .table_ocr import BoundingBox, DetectedTable, TableDetector

__all__ = [
    "BoundingBox",
    "DetectedTable",
    "DocumentParser",
    "DocumentStitcher",
    "ExtractedTextBlock",
    "PdfProcessingPipeline",
    "ParsedPage",
    "ProcessedDocument",
    "ProcessedTable",
    "StitchedPage",
    "TableDetector",
    "TableMarkdown",
]
