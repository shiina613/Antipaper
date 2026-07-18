"""Logging helpers that avoid leaking document contents or secrets."""

from __future__ import annotations

import logging
import re


_LOGGER_NAME = "antipaper.backend"
_SECRET_PATTERNS = (
    (re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^,\s]+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)(authorization)\s*[:=]\s*[^,\s]+"), r"\1=[REDACTED]"),
)


class SensitiveDataFilter(logging.Filter):
    """Redact common secret-like values from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not record.args:
            record.msg = self._redact(str(record.msg))
        return True

    @staticmethod
    def _redact(message: str) -> str:
        redacted = message
        for pattern, replacement in _SECRET_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the app logger and keep output body-safe."""

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        handler.addFilter(SensitiveDataFilter())
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.addFilter(SensitiveDataFilter())

    root_logger.setLevel(level)
    logging.getLogger(_LOGGER_NAME).setLevel(level)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the Antipaper namespace."""

    return logging.getLogger(_LOGGER_NAME if name is None else f"{_LOGGER_NAME}.{name}")
