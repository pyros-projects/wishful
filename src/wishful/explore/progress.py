"""Progress tracking and rich display for wishful.explore."""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from wishful.config import settings


@dataclass
class VariantResult:
    """Result of evaluating a single variant."""

    index: int
    status: str  # "generating", "testing", "passed", "failed", "error", "timeout"
    generation_time: float = 0.0
    test_passed: Optional[bool] = None
    benchmark_score: Optional[float] = None
    error_message: Optional[str] = None
    source_preview: Optional[str] = None


@dataclass
class ExploreProgress:
    """Tracks progress of an exploration run."""

    module_path: str
    function_name: str
    total_variants: int
    optimize_strategy: str
    has_benchmark: bool = False  # Whether a benchmark function is provided
    start_time: float = field(default_factory=time.perf_counter)
    results: List[VariantResult] = field(default_factory=list)
    current_variant: int = 0
    best_score: Optional[float] = None
    best_variant_index: Optional[int] = None
    first_passing_index: Optional[int] = None

    def record_generation_start(self, index: int) -> None:
        """Record that we're starting to generate a variant."""
        self.current_variant = index
        self.results.append(VariantResult(index=index, status="generating"))

    def record_generation_complete(
        self, index: int, generation_time: float, source: str
    ) -> None:
        """Record that generation completed."""
        if index < len(self.results):
            self.results[index].generation_time = generation_time
            self.results[index].status = "testing"
            # Store first 80 chars of source as preview
            self.results[index].source_preview = source[:80].replace("\n", " ")

    def record_test_result(
        self,
        index: int,
        passed: bool,
        score: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record test/benchmark result for a variant."""
        if index < len(self.results):
            result = self.results[index]
            result.test_passed = passed
            result.benchmark_score = score

            if error:
                result.status = "error"
                result.error_message = error[:80]
            elif passed:
                result.status = "passed"
                if self.first_passing_index is None:
                    self.first_passing_index = index
                if score is not None:
                    if self.best_score is None or score > self.best_score:
                        self.best_score = score
                        self.best_variant_index = index
            else:
                result.status = "failed"

    def record_timeout(self, index: int) -> None:
        """Record that a variant timed out."""
        if index < len(self.results):
            self.results[index].status = "timeout"
            self.results[index].error_message = "Generation timed out"

    def record_compile_error(self, index: int, error: str) -> None:
        """Record that a variant failed to compile."""
        if index < len(self.results):
            self.results[index].status = "error"
            self.results[index].error_message = f"Compile: {error[:60]}"

    @property
    def completed_count(self) -> int:
        return sum(
            1 for r in self.results if r.status not in ("generating", "testing")
        )

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "passed")

    @property
    def failed_count(self) -> int:
        return sum(
            1 for r in self.results if r.status in ("failed", "error", "timeout")
        )

    @property
    def elapsed_time(self) -> float:
        return time.perf_counter() - self.start_time

    def to_csv_rows(self) -> List[dict]:
        return [
            {
                "variant_index": r.index,
                "status": r.status,
                "generation_time": f"{r.generation_time:.3f}",
                "test_passed": r.test_passed,
                "benchmark_score": r.benchmark_score,
                "error_message": r.error_message or "",
            }
            for r in self.results
        ]


class AsyncExploreLiveDisplay:
    """Rich Live display for async exploration with real-time updates."""

    def __init__(self, progress: ExploreProgress, console: Optional[Console] = None):
        self.progress = progress
        self.console = console or Console()
        self._live: Optional[Live] = None
        self._progress_bar: Optional[Progress] = None

    def __enter__(self) -> "AsyncExploreLiveDisplay":
        self._progress_bar = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=self.console,
            expand=False,
        )
        self._task_id = self._progress_bar.add_task(
            f"Exploring {self.progress.function_name}",
            total=self.progress.total_variants,
        )
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *args) -> None:
        if self._live:
            self._live.__exit__(*args)

    def update(self) -> None:
        """Update the live display with current progress."""
        if self._progress_bar and self._task_id is not None:
            self._progress_bar.update(
                self._task_id, completed=self.progress.completed_count
            )
        if self._live:
            self._live.update(self._render())

    def _render(self) -> Panel:
        """Render the full progress display."""
        p = self.progress

        content_parts = []

        # Progress bar
        if self._progress_bar:
            content_parts.append(self._progress_bar)

        # Stats table
        stats_table = Table.grid(padding=(0, 2))
        stats_table.add_column(style="dim")
        stats_table.add_column(style="bold")

        stats_table.add_row("Strategy:", Text(p.optimize_strategy, style="cyan"))
        stats_table.add_row(
            "Passed:",
            Text(f"{p.passed_count}", style="green" if p.passed_count > 0 else "dim"),
        )
        stats_table.add_row(
            "Failed:",
            Text(f"{p.failed_count}", style="red" if p.failed_count > 0 else "dim"),
        )

        if p.best_score is not None:
            stats_table.add_row(
                "Best Score:", Text(f"{p.best_score:.2f}", style="yellow bold")
            )
            stats_table.add_row(
                "Best Variant:", Text(f"#{p.best_variant_index}", style="yellow")
            )

        content_parts.append(stats_table)

        # Results table
        if p.results:
            results_table = Table(
                title="Variants",
                show_header=True,
                header_style="bold",
                expand=True,
                padding=(0, 1),
            )
            results_table.add_column("#", width=3, justify="right")
            results_table.add_column("Status", width=10)
            results_table.add_column("Time", width=7, justify="right")
            # Only show Score column if benchmark is being used
            if p.has_benchmark:
                results_table.add_column("Score", width=10, justify="right")
            results_table.add_column("Info", overflow="ellipsis")

            # Show last 6 results
            for r in p.results[-6:]:
                status_style = {
                    "generating": "blue",
                    "testing": "cyan",
                    "passed": "green",
                    "failed": "red",
                    "error": "red bold",
                    "timeout": "yellow",
                }.get(r.status, "dim")

                time_text = (
                    f"{r.generation_time:.1f}s" if r.generation_time > 0 else "..."
                )
                info_text = r.error_message or r.source_preview or ""

                if p.has_benchmark:
                    score_text = (
                        f"{r.benchmark_score:.2f}" if r.benchmark_score is not None else "-"
                    )
                    results_table.add_row(
                        str(r.index),
                        Text(r.status, style=status_style),
                        time_text,
                        score_text,
                        Text(info_text[:40], style="dim"),
                    )
                else:
                    results_table.add_row(
                        str(r.index),
                        Text(r.status, style=status_style),
                        time_text,
                        Text(info_text[:40], style="dim"),
                    )

            content_parts.append(results_table)

        return Panel(
            Group(*content_parts),
            title=f"[bold magenta]🔍 wishful.explore[/] [dim]→[/] [cyan]{p.module_path}[/]",
            border_style="magenta",
            padding=(1, 2),
        )


# Keep the streaming printer as fallback for non-async usage
class ExploreProgressPrinter:
    """Streaming progress printer that outputs immediately (sync fallback)."""

    STATUS_SYMBOLS = {
        "generating": ("⏳", "cyan"),
        "testing": ("🔍", "blue"),
        "passed": ("✅", "green"),
        "failed": ("❌", "red"),
        "error": ("💥", "red bold"),
        "timeout": ("⏰", "yellow"),
    }

    def __init__(self, progress: ExploreProgress, console: Optional[Console] = None):
        self.progress = progress
        self.console = console or Console()
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True

        p = self.progress
        self.console.print()
        self.console.print(
            Panel(
                f"[bold cyan]{p.function_name}[/] from [dim]{p.module_path}[/]\n"
                f"[dim]Strategy:[/] {p.optimize_strategy} • "
                f"[dim]Variants:[/] {p.total_variants}",
                title="[bold magenta]🔍 wishful.explore[/]",
                border_style="magenta",
                padding=(0, 2),
            )
        )
        self.console.print()

    def on_generation_start(self, index: int) -> None:
        self.start()
        import sys
        self.console.print(
            f"  [cyan]⏳ Variant {index}/{self.progress.total_variants - 1}[/] "
            f"[dim]generating...[/]",
            end="",
        )
        sys.stdout.flush()

    def on_generation_complete(self, index: int, time_secs: float) -> None:
        import sys
        self.console.print(f" [dim]({time_secs:.1f}s)[/] ", end="")
        sys.stdout.flush()

    def on_test_start(self, index: int) -> None:
        import sys
        self.console.print("[blue]testing...[/] ", end="")
        sys.stdout.flush()

    def on_result(self, index: int, result: VariantResult) -> None:
        symbol, style = self.STATUS_SYMBOLS.get(result.status, ("?", "dim"))
        parts = [f"[{style}]{symbol} {result.status.upper()}[/]"]

        if result.benchmark_score is not None:
            parts.append(f"[yellow]score={result.benchmark_score:.2f}[/]")

        if result.error_message:
            parts.append(f"[dim]{result.error_message[:40]}...[/]")

        self.console.print(" ".join(parts))

    def on_timeout(self, index: int) -> None:
        self.console.print("[yellow]⏰ TIMEOUT[/]")

    def on_complete(self) -> None:
        p = self.progress

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="dim")
        table.add_column()

        table.add_row("Elapsed:", f"[cyan]{p.elapsed_time:.1f}s[/]")
        table.add_row(
            "Passed:",
            f"[green]{p.passed_count}[/]" if p.passed_count else "[dim]0[/]",
        )
        table.add_row(
            "Failed:",
            f"[red]{p.failed_count}[/]" if p.failed_count else "[dim]0[/]",
        )

        if p.best_score is not None:
            table.add_row("Best Score:", f"[yellow bold]{p.best_score:.2f}[/]")
            table.add_row("Best Variant:", f"[yellow]#{p.best_variant_index}[/]")

        self.console.print()
        self.console.print(
            Panel(
                table,
                title="[bold]Summary[/]",
                border_style="green" if p.passed_count > 0 else "red",
                padding=(0, 2),
            )
        )


def save_exploration_results(progress: ExploreProgress) -> Path:
    """Save exploration results to CSV in the cache directory."""
    explore_dir = settings.cache_dir / "_explore"
    explore_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{progress.function_name}_{timestamp}.csv"
    filepath = explore_dir / filename

    rows = progress.to_csv_rows()
    if rows:
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    # Summary file
    summary_path = explore_dir / f"{progress.function_name}_{timestamp}_summary.txt"
    with open(summary_path, "w") as f:
        f.write(f"Exploration Summary\n")
        f.write(f"==================\n\n")
        f.write(f"Module: {progress.module_path}\n")
        f.write(f"Function: {progress.function_name}\n")
        f.write(f"Strategy: {progress.optimize_strategy}\n")
        f.write(f"Total Variants: {progress.total_variants}\n")
        f.write(f"Elapsed Time: {progress.elapsed_time:.2f}s\n\n")
        f.write(f"Results:\n")
        f.write(f"  Passed: {progress.passed_count}\n")
        f.write(f"  Failed: {progress.failed_count}\n")
        if progress.best_score is not None:
            f.write(f"  Best Score: {progress.best_score:.4f}\n")
            f.write(f"  Best Variant: #{progress.best_variant_index}\n")

    return filepath
