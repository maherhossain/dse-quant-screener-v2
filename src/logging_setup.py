"""Logging configuration for the project.
Single entry point: setup_logging(name) -> logging.Logger.
Format matches the project rule: '%(asctime)s [%(levelname)s] %(message)s'.
Writes to logs/{name}.log (UTF-8) and to stderr. Idempotent: calling twice
with the same name returns the same logger without duplicating handlers.
"""
from __future__ import annotations
import logging
import sys
from src import paths
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_SENTINEL = "_dse_v2_configured"
def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger with file + stream handlers.
    Args:
        name: logger name; also used as the log filename stem.
        level: logging level for the logger and both handlers.
    Returns:
        A configured logging.Logger. Subsequent calls with the same name
        return the same logger, without adding duplicate handlers.
    """
    paths.ensure_dirs()
    logger = logging.getLogger(name)
    # Idempotency: if we've already configured this logger, return it as-is.
    if getattr(logger, _SENTINEL, False):
        return logger
    logger.setLevel(level)
    logger.propagate = False  # don't double-log through the root logger
    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
    log_file = paths.LOGS_DIR / f"{name}.log"
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(stream=sys.stderr)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    setattr(logger, _SENTINEL, True)
    return logger
__all__ = ["setup_logging"]