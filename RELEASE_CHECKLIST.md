# Release checklist

Every release is smoke-tested against real model calls, and the proof is
committed. Fake-LLM unit tests guard logic; real-model smoke tests with kept
evidence guard the product (see `STRATEGY.md`).

## Steps

1. **Green suite + gates**
   ```bash
   uv run pytest -q --cov=wishful --cov-report=term-missing   # coverage gate
   uv run ruff check .
   uv run mypy src/wishful   # advisory until the 2.x pass lands
   ```

2. **Real-model smoke run** (costs API spend; needs credentials in `.env`):
   ```bash
   WISHFUL_SMOKE=1 WISHFUL_PROOF_VERSION=<version> uv run pytest -m smoke
   ```
   This writes the proof bundle to `docs/proofs/<version>/summary.json`.

3. **Full example sweep** against the real model (the 15 `examples/*.py`):
   each example must succeed. Re-run policy below.

4. **Flake policy.** The model path is non-deterministic. Each example/smoke
   case may be retried **at most twice** within one release run; the full set
   must go green within that budget. Record *every* attempt (including red ones)
   in the proof notes — the bundle reports reliability, not just possibility. A
   case that stays red after the allowed retries blocks the release.

5. **Scan the proof bundle for secrets** before committing:
   ```bash
   gitleaks detect --no-git --source docs/proofs/<version>/   # or trufflehog
   ```
   The harness records only metadata and short result summaries (never prompts
   or generated source), but scan anyway.

6. **Commit the proof bundle** under `docs/proofs/<version>/`.

7. **Bump the version** in `pyproject.toml`, update the docs-site changelog,
   then tag. `__version__` derives from package metadata, so no source edit is
   needed.

8. **Publish.** Pushing the `pyproject.toml` version change to `main` triggers
   the publish workflow.

## Gate

Release is blocked unless `docs/proofs/<version>/summary.json` shows the full
example sweep and the four smoke cases green within the flake budget.
