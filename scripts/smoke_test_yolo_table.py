"""Run table-specific YOLOv8 inference on real PDF page images.

The script records only detection metadata and cropped regions. It deliberately
does not emit OCR text, cells, row/column counts, or Markdown because YOLOv8 is
an object detector rather than a text/table-structure recognizer.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
import sys

import fitz
from PIL import Image
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.pipeline.table_ocr import TableDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf",
        type=Path,
        default=PROJECT_ROOT / "data" / "01.pdf",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=PROJECT_ROOT / "models" / "table_detect_yolov8.pt",
    )
    parser.add_argument("--device", default="0")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--render-scale", type=float, default=2.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evidence" / "yolo_smoke",
    )
    return parser.parse_args()


def render_page(page: fitz.Page, scale: float) -> Image.Image:
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    if not args.pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {args.pdf}")
    if not args.model.is_file():
        raise FileNotFoundError(f"YOLO weights not found: {args.model}")
    if str(args.device).startswith("0") and not torch.cuda.is_available():
        raise RuntimeError("GPU smoke test requested but Torch cannot access CUDA")

    args.output.mkdir(parents=True, exist_ok=True)
    detector = TableDetector(
        args.model,
        confidence_threshold=args.confidence,
        device=args.device,
    )
    model = detector.load_model()
    records: list[dict[str, object]] = []
    started = perf_counter()

    with fitz.open(args.pdf) as document:
        page_count = min(document.page_count, args.max_pages)
        for page_index in range(page_count):
            image = render_page(document[page_index], args.render_scale)
            page_started = perf_counter()
            detections = detector.detect(image)
            page_seconds = perf_counter() - page_started
            crops = detector.crop_tables(image, [item.bbox for item in detections])

            page_detections: list[dict[str, object]] = []
            for detection_index, (detection, crop) in enumerate(
                zip(detections, crops), start=1
            ):
                crop_name = f"page_{page_index + 1:03d}_table_{detection_index:02d}.png"
                Image.fromarray(crop[:, :, ::-1]).save(args.output / crop_name)
                page_detections.append(
                    {
                        "bbox": list(detection.bbox),
                        "confidence": detection.confidence,
                        "class_id": detection.class_id,
                        "class_name": model.names.get(detection.class_id),
                        "crop": crop_name,
                    }
                )

            records.append(
                {
                    "page": page_index + 1,
                    "image_size": list(image.size),
                    "inference_seconds": page_seconds,
                    "detections": page_detections,
                }
            )

    payload = {
        "method": "YOLOv8 table detection only",
        "ocr_available": False,
        "pdf": str(args.pdf.resolve()),
        "model": str(args.model.resolve()),
        "model_sha256": file_sha256(args.model),
        "classes": model.names,
        "confidence_threshold": args.confidence,
        "requested_device": args.device,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "pages": records,
        "total_detections": sum(len(record["detections"]) for record in records),
        "total_seconds": perf_counter() - started,
    }
    benchmark_path = args.output / "benchmark.json"
    benchmark_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
