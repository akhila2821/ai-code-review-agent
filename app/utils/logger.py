"""
Structured logging setup using Python's standard logging library,
with rich formatting in development and JSON-compatible output in production.
"""

import logging
import sys
from app.config import get_settings

settings = get_settings()

_LOG_FORMAT_DEV = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
)
_LOG_FORMAT_PROD = (
    '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
    '"line":%(lineno)d,"message":"%(message)s"}'
)


def configure_logging() -> None:
    """Configure root logger once at application startup."""
    fmt = _LOG_FORMAT_DEV if settings.app_env == "development" else _LOG_FORMAT_PROD
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call configure_logging() once at startup."""
    return logging.getLogger(name)
