"""Structured logging helpers for wifi_recover."""

from __future__ import annotations

import logging
from typing import Any, Dict

_STANDARD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
}


class KeyValueFormatter(logging.Formatter):
    """Render log records as key=value pairs for easy parsing."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        base: Dict[str, Any] = {
            "level": record.levelname,
            "msg": record.message,
        }
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_ATTRS
        }
        parts = []
        for key, value in base.items():
            parts.append(f"{key}={self._format_value(value)}")
        for key in sorted(extras.keys()):
            parts.append(f"{key}={self._format_value(extras[key])}")
        return " ".join(parts)

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, str):
            return repr(value)
        return repr(value)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging with a structured formatter."""
    logger = logging.getLogger()
    logger.setLevel(level.upper())
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(KeyValueFormatter())
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
