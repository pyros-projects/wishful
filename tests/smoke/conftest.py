"""Smoke-test harness: real-model runs with kept proof.

Smoke tests are gated: they run only when ``WISHFUL_SMOKE=1`` and provider
credentials are present, so the normal (fake-LLM) suite and CI skip them. Each
smoke test records a proof entry via the ``proof`` fixture; at session end the
bundle is written to ``docs/proofs/<version>/summary.json``.

Proof content is metadata only — model id, timing, pass/fail, attempts, and a
short *result* summary. It never contains prompt text or generated source, so a
committed proof bundle cannot leak credentials or context.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

_CRED_VARS = ("OPENAI_API_KEY", "AZURE_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")
_results: list[dict] = []


def smoke_enabled() -> bool:
    return os.getenv("WISHFUL_SMOKE") == "1" and any(os.getenv(v) for v in _CRED_VARS)


def pytest_collection_modifyitems(config, items):
    if smoke_enabled():
        return
    skip = pytest.mark.skip(
        reason="smoke tests require WISHFUL_SMOKE=1 and provider credentials"
    )
    for item in items:
        # Match the @pytest.mark.smoke marker only — the directory name "smoke"
        # is itself a node keyword, so `"smoke" in item.keywords` over-matches.
        if item.get_closest_marker("smoke") is not None:
            item.add_marker(skip)


def build_summary(results: list[dict], version: str, model: str) -> dict:
    """Assemble the proof bundle payload (metadata only — no prompts/source)."""
    return {
        "version": version,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": sum(1 for r in results if r["status"] == "pass"),
        "failed": sum(1 for r in results if r["status"] != "pass"),
        "cases": results,
    }


@pytest.fixture
def proof():
    """Recorder used by smoke tests: proof(case, status, seconds=..., ...)."""

    def _record(case, status, *, seconds, attempts=1, output_summary=""):
        _results.append(
            {
                "case": case,
                "status": status,
                "seconds": round(seconds, 2),
                "attempts": attempts,
                # truncated, newline-free result summary — never source/prompts
                "output_summary": (output_summary or "")[:120].replace("\n", " "),
            }
        )

    return _record


def pytest_sessionfinish(session, exitstatus):
    if not _results:
        return
    import wishful

    version = os.getenv("WISHFUL_PROOF_VERSION", wishful.__version__)
    out_dir = Path("docs/proofs") / version
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = build_summary(_results, version, wishful.settings.model)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
