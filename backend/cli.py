"""Command-line entrypoint for the Antipaper backend."""

from __future__ import annotations

import argparse

import uvicorn

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
    args = build_parser().parse_args()
    configure_logging()
    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
