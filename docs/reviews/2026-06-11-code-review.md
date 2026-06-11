# Code Review — wishful whole-codebase release-readiness (v0.3.0)

- **Scope:** entire repository at `main` @ `4b0ab9b` (user-directed whole-repo review; no diff base). 103 tracked files, ~3.5k LOC in `src/wishful`.
- **Intent:** extensive polish pass before the v0.3.0 release — examples smoke-tested against real `gpt-5.5` with kept proof, feature/example coverage, doc freshness, code quality, architecture/design, dependency currency.
- **Mode:** default (interactive). **Fixes deliberately NOT applied** — the user's stated workflow is review → triage → `/ce-plan`; applying ~80 findings mid-review would preempt the plan.
- **Review team:** correctness, security, adversarial, testing, maintainability, project-standards, reliability, api-contract, architecture-strategist, agent-native + custom: smoke-tests (real LLM), docs-freshness, example-coverage, deps-currency. Skipped: learnings-researcher (no docs/solutions/), performance (LLM-latency-dominated), frontend/swift/migration (N/A).
- **Validation:** 16 independent validators covering all 20 merged P0/P1 claims — **20/20 confirmed, 0 dropped**.
- **Deterministic baseline:** 154 tests pass, coverage 78%; ruff 34 errors (20 auto-fixable); mypy 32 errors in 5 files; bandit 3 medium / 2 low.
- **Smoke proof:** `/tmp/compound-engineering/ce-code-review/20260611-023408-d3974d10/smoke/` (per-example logs + summary.json). 10/15 pass, 5 fail.

## Findings

### P0 — Critical

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 1 | `src/wishful/safety/validator.py:11` | Safety validator trivially bypassable; docs overstate guarantee | security (validated) | 100 |
| 2 | `src/wishful/llm/client.py:91` | No request timeout on litellm calls — imports can hang indefinitely | reliability (validated) | 100 |
| 3 | `src/wishful/llm/client.py:164` | gpt-5.5 returns empty content on 5/15 examples (litellm 1.80.0 lock) | smoke-tests, deps | 100 |

- **#1** — `__import__('os').system(...)`, `importlib.import_module('os')`, and `getattr(__builtins__,'eval')` all pass `validate_code` with safety ON; the open()-mode check is bypassed by any non-literal mode. README §"Safety Rails" claims these categories are blocked. Fix is two-sided: harden the validator (deny `__import__`/`importlib`/`builtins`/getattr-gadgets, non-literal open modes) AND rewrite the docs to present it as defense-in-depth, not a sandbox. The review gate cannot serve as backstop today because of #5.
- **#2** — `litellm.completion()`/`acompletion()` receive no `timeout` kwarg and Settings has no timeout field; litellm's default lets an import-time call hang for many minutes. Observed live: example 08 hit our 240s harness timeout mid-generation. Fix: `request_timeout` setting + env var, passed to both call sites.
- **#3** — `GenerationError: LLM returned empty content` on examples 00, 08(retry), 09, 10, 13 — all real `gpt-5.5` runs; failures cluster on dynamic-mode generations. Locked litellm 1.80.0 predates gpt-5.5 day-0 support (1.83.14); likely reasoning-token/max_tokens mis-mapping plus `max_tokens=4096`/`temperature=1.0` defaults unsuited to reasoning models. Fix together with #26 (bump litellm floor+lock), then re-run the smoke suite; add empty-content retry with actionable error.

### P1 — High

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 4 | `src/wishful/core/loader.py:131` | Failed generations permanently poison the static cache | correctness (validated) | 100 |
| 5 | `src/wishful/core/loader.py:107` | review=True executes code BEFORE approval; regen paths skip review | correctness, security (validated) | 100 |
| 6 | `src/wishful/core/loader.py:241` | review input() has no TTY guard — hangs/crashes headless | agent-native, architecture (P0/P3 → kept P1) | 100 |
| 7 | `src/wishful/core/loader.py:157` | SyntaxError retry path dead when safety on (validator raises ImportError) | correctness, adversarial (validated) | 100 |
| 8 | `src/wishful/llm/prompts.py:73` | Fence stripping leaves `python` tag → NameError module cached | correctness, adversarial (validated) | 100 |
| 9 | `src/wishful/logging.py:50` | `import wishful` destroys host app's loguru sinks | correctness, reliability (validated) | 100 |
| 10 | `src/wishful/explore/explorer.py:80` | nest_asyncio undeclared dep — explore() crashes in Jupyter | 4 reviewers (validated) | 100 |
| 11 | `src/wishful/core/loader.py:175` | hasattr/getattr probes fire LLM generation and overwrite cache | adversarial (validated) | 100 |
| 12 | `src/wishful/cache/manager.py:48` | Non-atomic cache writes — torn files on crash, racing processes | adversarial, reliability (validated) | 100 |
| 13 | `src/wishful/cache/manager.py:16` | static/dynamic collapse to same cache path — cross-namespace delete/overwrite | correctness, adversarial (validated) | 100 |
| 14 | `tests/conftest.py:16` | allow_unsafe=True globally — all 154 tests run with validator disabled | testing, adversarial (validated) | 100 |
| 15 | `tests/test_safety.py:1` | Validator 55% covered, 2 tests; _check_calls chain entirely untested | testing (claimed P0), standards (validated) | 100 |
| 16 | `STRATEGY.md:16` / `tests/` | Real-model smoke layer with kept proof: required, unimplemented | standards, testing (validated) | 100 |
| 17 | `src/wishful/explore/strategies.py:1` | Dead module — logic duplicated inline in explorer.py; 0% coverage | testing, maintainability, architecture (validated) | 100 |
| 18 | `src/wishful/explore/progress.py:290` | Dead class ExploreProgressPrinter (~100 lines, never referenced) | maintainability (validated) | 100 |
| 19 | `src/wishful/types/registry.py:211` | default_factory self-comparison bug — `<MISSING_TYPE>` garbage in prompts | correctness, maintainability (validated) | 100 |
| 20 | `src/wishful/__init__.py:105` | `__version__ = "0.1.0"` vs pyproject 0.2.4 → will ship wrong at 0.3.0 | 4 reviewers (validated) | 100 |
| 21 | `src/wishful/config.py:17` | Generic DEFAULT_MODEL silently beats WISHFUL_MODEL; docs imply opposite | api-contract, correctness, docs (validated) | 100 |
| 22 | `pyproject.toml:16` | pyglove runtime dep imported nowhere | deps, correctness (validated) | 100 |
| 23 | `pyproject.toml:11` | litellm floor >=1.40.0 / lock 1.80.0 predate Responses API + gpt-5.5 | deps (validated locally) | 95 |
| 24 | `src/wishful/evolve/evolver.py:26` | timeout_per_variant + verbose accepted but silently no-ops | reliability (claimed P0), 3 others (validated) | 100 |
| 25 | `src/wishful/__main__.py` | CLI output human prose only — no --json, no argparse | agent-native (validated) | 100 |
| 26 | `.env.template:1` | Documents 2 of ~13 env vars | agent-native (validated) | 100 |
| 27 | `README.md:338` / `pyproject.toml` | README shows bare `wishful` commands; no [project.scripts] exists | docs, api-contract (validated) | 100 |

- **#4** — LLM output is written to `.wishful/` before validation/exec; on SecurityError or non-SyntaxError exec failure the file survives, and every later import re-fails from cache with zero regeneration. One bad generation = permanently broken import until manual clear. (Cache-hit path does re-validate, but always against the same bad source.)
- **#5** — `exec_module` runs `_exec_source` at line 107 and asks "Run this code? [y/N]" at 110/114 — module top-level code has already executed. All four regeneration paths skip review entirely. README promises "approval before executing".
- **#6** — opt-in feature, but `WISHFUL_REVIEW=1` in CI/daemon = deadlock (input() with no isatty guard, no EOFError handling). Severity disagreement noted (agent-native P0, architecture P3); kept P1 since the default is off.
- **#7** — with safety ON (the default), the validator converts syntax errors to ImportError before exec, so the loader's regenerate-once `except SyntaxError` never fires. Masked by #14.
- **#8** — verified by running the function: ` ```python\n<code>\n``` ` strips to `python\n<code>` — parses as AST (bare name), NameErrors at exec, and via #4 poisons the cache. The standard LLM response shape, broken.
- **#9** — `logger.remove()` (no args) runs at import time and deletes all host-app sinks; empirically confirmed. A library must only remove its own handler ids.
- **#10** — `nest_asyncio` is imported when explore() runs inside a live event loop (the normal Jupyter case) and is in neither pyproject nor the venv: ModuleNotFoundError.
- **#11** — `getattr(mod, 'x', None)`/`hasattr` miss → `__getattr__` → unconditional generation + cache overwrite + module re-exec. Single-underscore names (IPython repr probes) included. Paid API calls from a probe.
- **#12** — `path.write_text` directly; no temp-file + `os.replace`, no locking.
- **#13** — `module_path()` strips both `static` and `dynamic` prefixes → same `.py` path; review-rejection/regenerate()/explore-winner against one namespace deletes or overwrites the other's file.
- **#14/#15** — the suite's safety blindness (validator disabled in every test) is precisely why #4, #7, #8 shipped. Hardening #1 without these tests will not stick.
- **#16** — this review's smoke sweep is the first-ever real-model run with proof; formalize as `tests/smoke/` + proof convention + release gate.
- **#19** — `field.default_factory is not field.default_factory` is always False; `tags: list[str] = field(default_factory=list)` serializes as `tags: list = <dataclasses._MISSING_TYPE object at 0x...>` into LLM prompts.
- **#21** — pick the contract: wishful-specific var should win; today a stale generic `DEFAULT_MODEL` silently overrides `WISHFUL_MODEL`.
- **#23** — fix jointly with P0 #3. Recommended: floor `>=1.83.14` (day-0 gpt-5.5 + completion→responses bridge; avoids quarantined 1.82.7/8), lock to current 1.88.x.
- **#24** — either implement (preferred: per-call timeout closes part of #2 for evolve) or remove params before 0.3.0 locks the API.
- **#27** — decide: add `[project.scripts] wishful = "wishful.__main__:main"` (nicer) or fix docs to `python -m wishful`.

### P2 — Moderate (consolidated)

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 28 | `src/wishful/core/loader.py:61` | Dynamic calls pay 2-3 generations each (proxy regen discarded) | correctness, adversarial (validated) | 100 |
| 29 | `src/wishful/logging.py:68` | Bare import creates `.wishful/_logs/` in CWD; unguarded on RO filesystems | reliability (validated) | 100 |
| 30 | `src/wishful/types/registry.py:248` | `_format_annotation` drops generics: list[str]→list, Optional[int]→Optional | correctness | 95 |
| 31 | `src/wishful/core/loader.py:151` | Regen `__dict__.clear()` wipes `__name__`/`__spec__` — breaks reload | adversarial | 100 |
| 32 | `src/wishful/explore/explorer.py:230` | Winner overwrites multi-symbol module; recovery deletes proven winner | adversarial | 75 |
| 33 | `src/wishful/explore/explorer.py:286` | No exec timeout; SystemExit escapes candidate execution | adversarial | 100 |
| 34 | `src/wishful/cache/manager.py:18` | Path traversal via crafted module name in regenerate/reimport/CLI | security | 75 |
| 35 | `src/wishful/explore/explorer.py:31` | Module-global cached event loop + atexit; nest_asyncio fallback mutates host loop | maintainability | 75 |
| 36 | `src/wishful/config.py:74` | Settings singleton on `builtins`, no thread safety; reload shims | maintainability, architecture | 100 |
| 37 | `src/wishful/core/loader.py:17` | 20-line monkeypatch-detection shim in hot path | maintainability | 75 |
| 38 | `tests/test_types.py:353` | F811 duplicate class — test doesn't verify re-registration | maintainability | 100 |
| 39 | `pyproject.toml` / CI | Coverage gate declared in AGENTS.md but unenforced (no --cov in CI, no fail_under) | standards | 100 |
| 40 | `src/wishful/llm/client.py:18` | `_FAKE_MODE` frozen at import — network-isolation guarantee fragile | standards | 100 |
| 41 | `coverage.json` | Stale committed artifact (84%, missing explore/evolve/logging; fresh run: 78%) | standards, orchestrator-verified | 100 |
| 42 | `src/wishful/llm/client.py:14` | Exceptions: no common WishfulError base (2 extend ImportError, 2 Exception) | api-contract | 100 |
| 43 | `src/wishful/__init__.py:82` | reimport() unannotated; py.typed surface has 32 mypy errors | api-contract | 100 |
| 44 | `src/wishful/explore/variant.py:23` | `__wishful_source__` conditionally absent vs docs' unconditional access | api-contract | 75 |
| 45 | `src/wishful/{explore,evolve}/__init__.py` | Subpackage `__all__` exports unreachable from top level | api-contract | 75 |
| 46 | `src/wishful/__init__.py:41` | `wishful.type` in `__all__` shadows builtin on star-import | api-contract, correctness | 100 |
| 47 | `src/wishful/explore/explorer.py:308` | explore/evolve duplicate compile-exec; no shared seam for casefiles | architecture | 100 |
| 48 | `src/wishful/evolve/mutation.py:36` | evolve sync vs explore async LLM path divergence | architecture | 100 |
| 49 | `src/wishful/evolve/evolver.py:151` | No EvolutionResult type — dunder-dict contract about to freeze at 0.3.0 | architecture | 100 |
| 50 | `src/wishful/core/discovery.py:14` | context_radius module global — outside Settings/configure/reset | architecture, agent-native | 100 |
| 51 | `src/wishful/explore/progress.py:404` | CSV evidence path diverges from spec-003 layout | architecture | 100 |
| 52 | `src/wishful/types/registry.py:276` | Type registry never cleared in conftest autouse fixture | architecture | 75 |
| 53 | `src/wishful/explore/explorer.py:259` | explore passes context=None — type registry silently bypassed | architecture | 100 |
| 54 | `src/wishful/explore/explorer.py:97` | verbose=True default emits ANSI in non-TTY; save_results unbounded CSVs | agent-native | 75 |
| 55 | `pyproject.toml:20` | uv_build cap <0.10.0 excludes current 0.11.x — release-blocking on fresh CI | deps | 100 |
| 56 | `pyproject.toml` | Floors/locks stale: rich 13.7→15, ruff 0.14.6→0.15.16, mypy 1.18→2.1, pydantic lock | deps | 100 |
| 57 | `README.md` | Structure drift: "112 tests" vs 154, tree omits evolve/, examples list partial | docs | 100 |
| 58 | `AGENTS.md` | Drift across 8 sections: deps, evolve/ + logging.py missing, API list, test list/counts | docs | 100 |
| 59 | `docs-site/` | Changelog ends at 0.2.0; explore page not in sidebar; no evolve page | docs | 100 |
| 60 | `README.md:421`, `docs-site quickstart:64` | Bare `python` commands violate the repo's uv-only rule | standards | 100 |
| 61 | `examples/` | Missing example coverage: return_all, keep_history/history_limit, EvolutionError, CLI, review=True | example-coverage | 75 |
| 62 | `tests/` | Untested branches bundle: _extract_content errors, fence branches, config precedence, registry v1/TypedDict, finder install-twice, _ensure_symbols | testing | 100 |

### P3 — Low

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 63 | `src/wishful/explore/explorer.py:155` | Path validation accepts non-importable 3-part paths; winner cached to dead file | correctness | 80 |
| 64 | `src/wishful/explore/explorer.py:24` | Global warning filter suppresses users' coroutine warnings | correctness | 90 |
| 65 | 5 files | mypy 32-error bundle (registry `type` shadow, discovery Optional, progress types) | correctness | 100 |
| 66 | `src/wishful/config.py:160` | reset_defaults() env-snapshot inconsistency (cache_dir re-reads env) | correctness | 80 |
| 67 | `src/wishful/evolve/evolver.py:55` | fitness(original_fn) exception escapes uncaught | correctness | 80 |
| 68 | `src/wishful/__init__.py:9` | Cache alias import shadows wishful.cache subpackage attribute | adversarial | 100 |
| 69 | `src/wishful/core/finder.py:41` | Nested wishes (a.b) waste an LLM call then fail "not a package" | adversarial | 100 |
| 70 | `src/wishful/config.py:44` | CWD-relative cache_dir splits cache on chdir | adversarial | 75 |
| 71 | `src/wishful/explore/progress.py:89` | ExplorationError failures truncated to 60-80 chars | agent-native | 75 |
| 72 | ruff | Trivials: F401 ×3, F541 ×3 (20 auto-fixable total via `ruff check --fix`) | maintainability | 100 |
| 73 | `pyproject.toml` dev | Dev-dep lock refreshes (bandit/coverage/pytest/pytest-cov) | deps | 100 |
| 74 | `examples/` | P3 bundle: system_prompt, FAKE_LLM guidance, SecurityError demo, configure params, 11_logging near-dup of 01 | example-coverage | 75 |

## Smoke Test Results (real gpt-5.5, proof kept)

| Example | Status | Time | Note |
|---------|--------|------|------|
| 00_quick_start | FAIL | 175s | empty content (2nd static import) |
| 01-07 | PASS | — | incl. typed outputs, web scraping |
| 08_dynamic_vs_static | FAIL | 240s+242s | run 1: harness timeout mid-regen; retry: empty content |
| 09_context_shenanigans | FAIL | 90s | empty content on dynamic import |
| 10_cosmic_horror | FAIL | 150s | empty content on dynamic import |
| 11_logging | PASS | 81s | |
| 12_explore | PASS | 306s | real explore works |
| 13_explore_advanced | FAIL | 216s | no valid variants (LLM-as-judge) |
| 14_evolve | PASS | 32s | real evolution, fitness 689→812 |

Proof: `/tmp/compound-engineering/ce-code-review/20260611-023408-d3974d10/smoke/` — per-example logs + `summary.json`. **Note: /tmp is volatile; the polish plan should move these under the repo's future proof convention (#16).**

## Coverage

- **Applied: 0** — deliberately deferred to the polish plan per user's workflow (review → triage → plan). All findings remain in the actionable queue.
- **Validation:** 16 validator groups dispatched over all 20 merged P0/P1 claims; 20/20 confirmed; 0 infra failures.
- **Orchestrator direct verification:** 1 finding **rejected** — docs-freshness claimed the README coverage badge (78%) was stale vs coverage.json (84%); a fresh coverage run shows 78%, so the badge is correct and the stale artifact is the committed `coverage.json` (now finding #41).
- **Suppressed below anchor 75:** prompt-injection via context discovery (P2@60), debug-log credential leakage (P3@55), site-packages frame-filter leak (P2@70), non-TTY ANSI from ui.py Console (P2@50), `__wishful_evolution__` unversioned dict (P3@50) — carried as residual risks below.
- **Demoted (testing/maintainability advisory):** cache-manager helper tests, evolve arg-validation tests → testing gaps.
- **Reviewer incidents:** first persona dispatch wave failed on wrong agent-type names (recovered, full re-dispatch); smoke agent interrupted by user mid-sweep (orchestrator completed examples 08-14 with identical methodology; first-sweep logs preserved).
- **Skipped reviewers:** learnings-researcher (no docs/solutions/ directory), performance (LLM-latency-dominated library).
- **Residual risks (top):** in-process exec of LLM code is by design — no validator makes it safe, only an out-of-process sandbox would; prompt-injection via discovery context and runtime-arg repr() into prompts; dynamic-mode thread safety (clear+re-exec races); committed `.wishful/` cache files as a supply-chain vector given #1; review-gate crash on EOF in non-interactive stdin.
- **Testing gaps (union, beyond #14/#15):** no fenced-response e2e test; no review-ordering test; no loguru-survival test; no Jupyter/running-loop explore test; no cross-process cache race tests; no version-sync test; no `from wishful import *` test.

## Verdict

**Not ready** for v0.3.0 from current `main` — release-gating issues confirmed at every layer: the real-model path fails for the configured model (#3), imports can hang (#2) or stay permanently broken (#4, #8), `import wishful` damages host apps (#9), and the version string itself is wrong (#20).

Recommended fix order for the plan:
1. **Make the model path work:** #23 litellm bump → re-run smoke → #3 empty-content retry/diagnostics; #2 request timeout.
2. **Make generation honest:** #8 fence stripping, #4 cache poisoning, #7 dead retry, #12/#13 cache atomicity+namespacing.
3. **Make safety honest:** #1 validator hardening + docs truth, #5 review-before-exec, #6 TTY guard, #14/#15 test the validator with safety ON.
4. **Make the API honest for 0.3.0:** #20 version, #21 precedence, #24 no-op params, #22 pyglove, #10 nest_asyncio, #46 type shadow, #42 exception base, #27 CLI entry decision.
5. **Hygiene + docs:** #17/#18 dead code, ruff/mypy bundles, README/AGENTS/docs-site drift, example coverage, #16 smoke harness + proof convention (institutionalize what this review did by hand).
