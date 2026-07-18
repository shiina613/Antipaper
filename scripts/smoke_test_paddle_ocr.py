"""Run PP-StructureV3 against a real table rendered from a repository PDF.

The script uses PyMuPDF only to locate a reference table and establish expected
row/column counts. The actual input to ``PaddleOcrAdapter`` is PNG bytes, which
matches the production handoff contract.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter
from typing import Any

import fitz
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pipeline.paddle_ocr import PaddleOcrAdapter, PaddleOcrBackend


@dataclass(frozen=True)
class Candidate:
    pdf_path: Path
    page_number: int
    bbox: tuple[float, float, float, float]
    row_count: int
    column_count: int
    nonempty_ratio: float
    score: float


def find_candidate(pdf_paths: list[Path], max_pages_per_pdf: int) -> Candidate:
    candidates: list[Candidate] = []
    for pdf_path in pdf_paths:
        with fitz.open(pdf_path) as document:
            for page_index in range(min(document.page_count, max_pages_per_pdf)):
                page = document[page_index]
                for table in page.find_tables().tables:
                    rows = table.extract()
                    row_count = int(table.row_count)
                    column_count = int(table.col_count)
                    if not (3 <= row_count <= 20 and 2 <= column_count <= 8):
                        continue
                    total_cells = max(row_count * column_count, 1)
                    nonempty = sum(
                        bool(str(cell).strip())
                        for row in rows
                        for cell in row
                        if cell is not None
                    )
                    nonempty_ratio = nonempty / total_cells
                    if nonempty_ratio < 0.55:
                        continue
                    x0, y0, x1, y1 = (float(value) for value in table.bbox)
                    area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
                    # Prefer compact, regular tables whose structure can be
                    # independently checked without a subjective OCR review.
                    score = nonempty_ratio * 1_000_000 + area - row_count * 100
                    candidates.append(
                        Candidate(
                            pdf_path=pdf_path,
                            page_number=page_index + 1,
                            bbox=(x0, y0, x1, y1),
                            row_count=row_count,
                            column_count=column_count,
                            nonempty_ratio=nonempty_ratio,
                            score=score,
                        )
                    )
    if not candidates:
        raise RuntimeError("No suitable 3-20 row, 2-8 column table found")
    return max(candidates, key=lambda candidate: candidate.score)


def render_crop(candidate: Candidate, scale: float) -> bytes:
    with fitz.open(candidate.pdf_path) as document:
        page = document[candidate.page_number - 1]
        page_rect = page.rect
        x0, y0, x1, y1 = candidate.bbox
        clip = fitz.Rect(x0 - 3, y0 - 3, x1 + 3, y1 + 3) & page_rect
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(scale, scale),
            clip=clip,
            alpha=False,
        )
        return pixmap.tobytes("png")


def render_vietnamese_table_fixture() -> tuple[bytes, dict[str, Any]]:
    """Create deterministic table pixels; OCR still uses the real model."""

    rows = [
        ["Hạng mục", "Đơn vị phụ trách", "Tiến độ"],
        ["Kinh phí", "Sở Tài chính", "Quý III"],
        ["Hạ tầng", "Sở Thông tin và Truyền thông", "Quý IV"],
        ["Đào tạo", "Ủy ban nhân dân huyện", "Tháng 12"],
    ]
    widths = [300, 560, 240]
    row_height = 105
    margin = 24
    width = sum(widths) + margin * 2
    height = row_height * len(rows) + margin * 2
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 34)
    bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 34)

    x_positions = [margin]
    for cell_width in widths:
        x_positions.append(x_positions[-1] + cell_width)
    y_positions = [margin + index * row_height for index in range(len(rows) + 1)]
    for x in x_positions:
        draw.line((x, margin, x, height - margin), fill="black", width=4)
    for y in y_positions:
        draw.line((margin, y, width - margin, y), fill="black", width=4)

    for row_index, row in enumerate(rows):
        selected_font = bold if row_index == 0 else font
        for column_index, cell_text in enumerate(row):
            left = x_positions[column_index]
            top = y_positions[row_index]
            cell_width = widths[column_index]
            lines: list[str] = []
            current = ""
            for word in cell_text.split():
                candidate_text = f"{current} {word}".strip()
                if draw.textbbox((0, 0), candidate_text, font=selected_font)[2] <= cell_width - 28:
                    current = candidate_text
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
            line_height = 38
            text_top = top + (row_height - line_height * len(lines)) / 2
            for line_index, line in enumerate(lines):
                draw.text(
                    (left + 14, text_top + line_index * line_height),
                    line,
                    fill="black",
                    font=selected_font,
                )

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), {
        "kind": "generated_vietnamese_grid_fixture",
        "page_number": 1,
        "bbox": [0.0, 0.0, float(width), float(height)],
        "row_count": len(rows),
        "column_count": len(rows[0]),
        "expected_cells": rows,
    }


def package_versions(device_requested: str) -> dict[str, Any]:
    import paddle
    import paddleocr
    import torch

    return {
        "python": platform.python_version(),
        "paddlepaddle": paddle.__version__,
        "paddleocr": paddleocr.__version__,
        "torch": torch.__version__,
        "device_requested": device_requested,
        "paddle_default_device": paddle.device.get_device(),
        "compiled_with_cuda": paddle.device.is_compiled_with_cuda(),
        "cuda_device_count": paddle.device.cuda.device_count(),
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, help="Optional single PDF to scan")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--scale", type=float, default=2.5)
    parser.add_argument("--device", default="gpu:0")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "evidence" / "ocr_smoke",
    )
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument("--render-only", action="store_true")
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()

    if args.synthetic:
        image_bytes, candidate_payload = render_vietnamese_table_fixture()
        expected_rows = int(candidate_payload["row_count"])
        expected_columns = int(candidate_payload["column_count"])
        page_number = 1
        bbox = tuple(candidate_payload["bbox"])
    else:
        pdf_paths = (
            [args.pdf.resolve()]
            if args.pdf
            else sorted(path.resolve() for path in (PROJECT_ROOT / "data").glob("*.pdf"))
        )
        candidate = find_candidate(pdf_paths, args.max_pages)
        candidate_payload = {
            **asdict(candidate),
            "pdf_path": str(candidate.pdf_path.relative_to(PROJECT_ROOT)),
        }
        if args.scan_only:
            print(json.dumps(candidate_payload, ensure_ascii=False, indent=2))
            return 0
        image_bytes = render_crop(candidate, args.scale)
        expected_rows = candidate.row_count
        expected_columns = candidate.column_count
        page_number = candidate.page_number
        bbox = candidate.bbox

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "table_crop.png").write_bytes(image_bytes)
    if args.render_only:
        print(json.dumps(candidate_payload, ensure_ascii=False, indent=2))
        return 0

    # PaddleOCR/PaddleX imports ModelScope, which imports Torch. On Windows,
    # Torch must load before Paddle CUDA to avoid a native shm.dll collision.
    import torch  # noqa: F401
    import paddle

    if args.device.startswith("gpu") and (
        not paddle.device.is_compiled_with_cuda()
        or paddle.device.cuda.device_count() < 1
    ):
        raise RuntimeError("GPU smoke test requested but Paddle cannot access a CUDA GPU")

    started = perf_counter()
    table = PaddleOcrAdapter(PaddleOcrBackend(device=args.device)).ocr_table(
        image_bytes,
        page=page_number,
        bbox=bbox,
    )
    elapsed_seconds = perf_counter() - started
    structure_match = (
        table.row_count == expected_rows
        and table.column_count == expected_columns
    )

    table_payload = table.model_dump(mode="json")
    write_json(output_dir / "table.json", table_payload)
    (output_dir / "table.md").write_text(table.markdown, encoding="utf-8")
    benchmark = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source": candidate_payload,
        "runtime": package_versions(args.device),
        "elapsed_seconds": elapsed_seconds,
        "recognized": {
            "row_count": table.row_count,
            "column_count": table.column_count,
            "cell_count": len(table.cells),
            "confidence": table.confidence,
        },
        "row_column_match": structure_match,
        "artifacts": {
            "crop": "table_crop.png",
            "json": "table.json",
            "markdown": "table.md",
        },
    }
    write_json(output_dir / "benchmark.json", benchmark)
    print(json.dumps(benchmark, ensure_ascii=False, indent=2))
    return 0 if structure_match else 2


if __name__ == "__main__":
    raise SystemExit(main())
