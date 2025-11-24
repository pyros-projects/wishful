from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from loguru import logger
from rich.logging import RichHandler

from wishful.config import settings


_configured = False


def _log_dir() -> Path:
    return settings.cache_dir / "_logs"


def _configure_rich_console(level: str):
    # Configure a dedicated logger using RichHandler
    handler = RichHandler(
        show_time=True,
        show_level=True,
        show_path=True,
        enable_link_path=True,
        rich_tracebacks=True,
        markup=True,
        log_time_format="%H:%M:%S.%f",
    )
    handler.setLevel(level)

    import logging

    rich_logger = logging.getLogger("wishful.rich")
    rich_logger.handlers.clear()
    rich_logger.propagate = False
    rich_logger.setLevel(level)
    rich_logger.addHandler(handler)
    return rich_logger


def configure_logging(force: bool = False) -> None:
    global _configured

    # Avoid repeated reconfiguration unless forced
    if _configured and not force:
        return

    logger.remove()

    level = (settings.log_level or ("DEBUG" if settings.debug else "WARNING")).upper()

    # Console sink: only when debug or level <= INFO
    # Console via RichHandler for nicer TTY output
    rich_logger = _configure_rich_console(level)
    logger.add(
        lambda m: rich_logger.log(
            m.record["level"].no,
            f"{m.record['module']}:{m.record['function']}:{m.record['line']} | {m.record['message']}",
        ),
        level=level,
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )

    if settings.log_to_file:
        log_dir = _log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        logfile = log_dir / f"{datetime.now():%Y-%m-%d}.log"
        logfile.touch(exist_ok=True)
        logger.add(
            str(logfile),
            level=level,
            enqueue=False,
            backtrace=False,
            diagnose=False,
            rotation=None,
            retention=None,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
        )

    _configured = True


# Configure once at import time with defaults
configure_logging()
