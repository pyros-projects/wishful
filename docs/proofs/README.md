# Release proofs

Each subdirectory is named for a released version and holds the **kept proof**
that the version was smoke-tested against real model calls before shipping (per
`STRATEGY.md` and `RELEASE_CHECKLIST.md`).

## What's here

```
docs/proofs/<version>/summary.json
```

`summary.json` is written by the smoke harness (`tests/smoke/`) and records, per
case: the name, pass/fail, wall-clock seconds, attempt count, and a short
**result** summary — plus the model id and a timestamp. It contains **metadata
only**: never prompt text, caller source, or generated code, so a committed
bundle cannot leak credentials or context.

## Regenerating

```bash
WISHFUL_SMOKE=1 WISHFUL_PROOF_VERSION=<version> uv run pytest -m smoke
```

Smoke tests are skipped unless `WISHFUL_SMOKE=1` and provider credentials are
present, so the normal suite and CI never make API calls.
