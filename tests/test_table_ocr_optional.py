from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_yolo_dependency_is_loaded_only_when_detector_is_enabled() -> None:
    script = """
import sys
sys.modules["ultralytics"] = None
from pipeline.table_ocr import TableDetector
try:
    TableDetector(model_path="missing.pt").load_model()
except RuntimeError as exc:
    assert "ultralytics is required only" in str(exc)
else:
    raise AssertionError("YOLO unexpectedly loaded")
"""
    environment = os.environ.copy()
    root = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = os.pathsep.join((str(root), str(root / "src")))

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )

    assert result.returncode == 0, result.stderr
