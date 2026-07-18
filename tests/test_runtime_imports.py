"""Regression tests for the repository-root backend entry point."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_backend_main_imports_without_src_on_pythonpath(tmp_path: Path) -> None:
    """Match ``scripts/run_backend.ps1`` instead of pytest's augmented path."""

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["ARTIFACT_DIR"] = str(tmp_path / "artifacts")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend.main import app; assert app.title == 'Antipaper API'",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
