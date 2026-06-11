from __future__ import annotations

from datetime import datetime
from pathlib import Path

from loguru import logger
from rich.logging import RichHandler

from wishful.config import settings


_configured = False
# Only these sink ids belong to wishful; we never touch sinks the host added.
_wishful_sink_ids: list[int] = []
_file_log_warned = False
_bootstrap_removed = False


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
    global _configured, _file_log_warned, _bootstrap_removed

    # Avoid repeated reconfiguration unless forced
    if _configured and not force:
        return

    # Remove loguru's default bootstrap sink (id 0) exactly once. It is loguru's
    # own auto-installed stderr handler at DEBUG level — not a host-added sink — so
    # leaving it in place made every record print twice (its plain stderr output
    # plus wishful's Rich console sink) and leaked wishful's own DEBUG internals to
    # the host's stderr even at the default WARNING level. We install our own
    # console sink below, so the default is redundant. Host-added sinks keep their
    # own ids (>= 1) and are never touched.
    if not _bootstrap_removed:
        try:
            logger.remove(0)
        except ValueError:
            pass  # the host already removed loguru's default before importing us
        _bootstrap_removed = True

    # Remove ONLY wishful's own sinks — never bare logger.remove(), which would
    # delete sinks the host application installed before importing wishful.
    for sink_id in _wishful_sink_ids:
        try:
            logger.remove(sink_id)
        except ValueError:
            pass
    _wishful_sink_ids.clear()

    level = (settings.log_level or ("DEBUG" if settings.debug else "WARNING")).upper()

    # Console sink via RichHandler for nicer TTY output
    rich_logger = _configure_rich_console(level)
    console_id = logger.add(
        lambda m: rich_logger.log(
            m.record["level"].no,
            f"{m.record['module']}:{m.record['function']}:{m.record['line']} | {m.record['message']}",
        ),
        level=level,
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )
    _wishful_sink_ids.append(console_id)

    if settings.log_to_file:
        try:
            log_dir = _log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            logfile = log_dir / f"{datetime.now():%Y-%m-%d}.log"
            logfile.touch(exist_ok=True)
            file_id = logger.add(
                str(logfile),
                level=level,
                enqueue=False,
                backtrace=False,
                diagnose=False,
                rotation=None,
                retention=None,
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
            )
            _wishful_sink_ids.append(file_id)
        except OSError as exc:
            # A read-only or full filesystem must not crash an import; degrade
            # to console-only logging with a single warning.
            if not _file_log_warned:
                logger.warning(
                    "wishful: file logging disabled (cannot write {}): {}",
                    _log_dir(),
                    exc,
                )
                _file_log_warned = True

    _configured = True


# Configure once at import time with defaults
configure_logging()
