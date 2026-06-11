"""Always-on tests for the smoke harness itself (no API calls).

These verify the gate and the proof-bundle schema without running the gated
real-model tests, so CI exercises the harness on every run.
"""

from __future__ import annotations

from tests.smoke.conftest import build_summary, smoke_enabled


def test_smoke_disabled_without_env(monkeypatch):
    monkeypatch.delenv("WISHFUL_SMOKE", raising=False)
    assert smoke_enabled() is False


def test_smoke_disabled_without_credentials(monkeypatch):
    monkeypatch.setenv("WISHFUL_SMOKE", "1")
    for var in ("OPENAI_API_KEY", "AZURE_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert smoke_enabled() is False


def test_smoke_enabled_with_env_and_credential(monkeypatch):
    monkeypatch.setenv("WISHFUL_SMOKE", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert smoke_enabled() is True


def test_proof_summary_schema():
    results = [
        {"case": "static_import:x", "status": "pass", "seconds": 1.2, "attempts": 1, "output_summary": "[12, 3]"},
        {"case": "explore:y", "status": "fail", "seconds": 3.4, "attempts": 2, "output_summary": "no winner"},
    ]
    summary = build_summary(results, version="9.9.9", model="openai/gpt-5.5")
    assert summary["version"] == "9.9.9"
    assert summary["model"] == "openai/gpt-5.5"
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["cases"] == results
    assert "generated_at" in summary
    # Proof must never carry prompt/source bodies — only metadata fields.
    for case in summary["cases"]:
        assert set(case) == {"case", "status", "seconds", "attempts", "output_summary"}
