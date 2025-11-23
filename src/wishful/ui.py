from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from wishful.config import settings

_console = Console()


@contextmanager
def spinner(message: str) -> Iterator[None]:
    if not settings.spinner:
        yield
        return

    with Progress(SpinnerColumn(), TextColumn(message), console=_console, transient=True) as progress:
        task_id = progress.add_task(message, total=None)
        try:
            yield
        finally:
            progress.update(task_id, completed=1)
            progress.stop()
