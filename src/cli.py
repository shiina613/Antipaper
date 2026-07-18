"""Command-line entrypoint for the Antipaper backend."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from .logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Antipaper backend API.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to.")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind to.")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for dev.")
    parser.add_argument(
        "--log-level",
        default="info",
        choices=("critical", "error", "warning", "info", "debug", "trace"),
        help="Uvicorn log level.",
    )
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()
    configure_logging()
    uvicorn.run(
        "src.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(Path(__file__).resolve().parent)] if args.reload else None,
        reload_excludes=[".runtime", "frontend", ".git", "node_modules", "__pycache__"] if args.reload else None,
        log_level=args.log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
