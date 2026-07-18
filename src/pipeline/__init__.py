"""Data extraction pipeline components with dependency-lazy exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    "BoundingBox": ("table_ocr", "BoundingBox"),
    "DetectedTable": ("table_ocr", "DetectedTable"),
    "DocumentParser": ("pdf_parser", "DocumentParser"),
    "DocumentStitcher": ("stitcher", "DocumentStitcher"),
    "ExtractedTextBlock": ("pdf_parser", "ExtractedTextBlock"),
    "PdfProcessingPipeline": ("processor", "PdfProcessingPipeline"),
    "ParsedPage": ("pdf_parser", "ParsedPage"),
    "ProcessedDocument": ("processor", "ProcessedDocument"),
    "ProcessedTable": ("processor", "ProcessedTable"),
    "StitchedPage": ("stitcher", "StitchedPage"),
    "TableDetector": ("table_ocr", "TableDetector"),
    "TableMarkdown": ("stitcher", "TableMarkdown"),
    "YoloModelConfigurationError": ("table_ocr", "YoloModelConfigurationError"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(f".{module_name}", __name__), attribute_name)
    globals()[name] = value
    return value
