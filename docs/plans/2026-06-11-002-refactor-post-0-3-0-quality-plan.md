---
title: "refactor: post-0.3.0 quality — behavioral P2s, architecture seams, examples"
type: refactor
date: 2026-06-11
origin: docs/reviews/2026-06-11-code-review.md
---

# refactor: post-0.3.0 quality — behavioral P2s, architecture seams, examples

## Summary

Everything from the 2026-06-11 whole-codebase review that is confirmed but not release-gating: behavioral P2 fixes (dynamic-mode economics, regeneration integrity, explore robustness), security depth beyond the 0.3.0 validator hardening, the architecture seams that prepare spec 003 (maintained imports / casefiles), example-coverage additions, and residual test debt. Companion to `docs/plans/2026-06-11-001-fix-v0-3-0-release-readiness-plan.md`; execute after v0.3.0 ships.

## Problem Frame

The release plan makes 0.3.0 honest; this plan makes the codebase ready for where STRATEGY.md points next. The review confirmed real but non-blocking defects (every dynamic call pays 2–3 generations; module regeneration wipes `__name__`/`__spec__`; explore can destroy a proven winner; candidates can hang or `sys.exit` the host) and identified the seams the active-import/casefile work (spec 003) will need — cheaper to plant now than to retrofit.

---

## Requirements

**Behavioral correctness**

- R1. A dynamic-mode function call costs exactly one generation; failed regenerations never leave a module half-populated. (review #28)
- R2. Module re-execution preserves `__name__`, `__spec__`, `__loader__`; `importlib.reload` works on wishful modules. (review #31)
- R3. explore's winner caching merges into multi-symbol modules instead of overwriting, and missing-symbol recovery never deletes a proven winner. (review #32)
- R4. explore/evolve candidate execution is time-bounded and contains `BaseException` (including `SystemExit`); user callables cannot hang or kill the host. (review #33)
- R5. explore's event-loop handling drops the module-global cached loop + atexit pattern in favor of `asyncio.run` (or an equivalent owned-loop design); behavior inside running loops (Jupyter) is tested. (review #35)
- R6. `ExplorationError` carries full, untruncated failure messages. (review #71)

**Security depth**

- R7. Cache path mapping rejects traversal (no `..`/separators; resolved paths must stay inside `cache_dir`) across `regenerate`, `reimport`, and the CLI. (review #34)
- R8. Discovery context is delimited as untrusted data in prompts and capped in size; debug logging redacts prompt bodies unless explicitly opted in. (review residual risks)

**Architecture seams (spec-003 preparation)**

- R9. One shared compile-and-exec helper serves explorer and evolver — the future casefile hook point. (review #47)
- R10. `evolve()` returns an `EvolutionResult` (fn, history, best_score) that proxies the winner's `__name__`/`__doc__`/`__wishful_source__`/`__wishful_evolution__` so `evolve(evolve(fn))` and `inspect.signature()` keep working; `__wishful_evolution__` gains a versioned TypedDict schema. No silent-no-op `accept()` (see KTD). (review #49; suppressed "__wishful_evolution__ unversioned dict" P3@50)
- R11. `context_radius` lives in Settings (configure/reset aware); `set_context_radius()` becomes a thin wrapper. (review #50)
- R12. explore's generation calls receive the registered type context instead of `None`. (review #53)
- R13. The explore CSV path is marked legacy pending the spec-003 evidence layout (the `registry_path()` seam is intentionally deferred: spec-003 Open Decision 4 leaves `.wishful/evidence/` vs `.wishful/runs/` undecided, so a stub now would commit to an unchosen layout — it is a one-line addition once decided). (review #51)
- R14. Global state is tamed for tests and threads: `configure()` under a lock, type registry cleared in the conftest autouse fixture, the loader's monkeypatch-detection shim replaced by an injectable generate function. (review #36, #52, #37)

**Developer experience**

- R15. Every public feature has example coverage: `explore(return_all=True)`, evolve `keep_history`/`history_limit`, `EvolutionError` handling, CLI (`--json`), `review=True`, `SecurityError`/`allow_unsafe`, `configure(model/temperature/max_tokens)`, `reset_defaults()`; `11_logging.py` earns its file; `09_context_shenanigans.py` gets a docstring. (review #61, #74)
- R16. Residual test debt closed: registry pydantic-v1/TypedDict discrimination, finder double-install guard, `_ensure_symbols` failure path, cache helper functions, evolve argument validation, Windows path normalization in discovery. (review #62, demoted items)
- R17. Remaining paper cuts: nested wishes (`wishful.static.a.b`) rejected with a clear error before any LLM call; `cache_dir` resolved to an absolute path at configure time; the coroutine-warning filter scoped to wishful's own calls; mypy 2.x adopted. (review #69, #70, #64, #56-mypy)

---

## Key Technical Decisions

- **Dynamic proxy: lazy single generation.** Drop the eager regeneration in `__getattribute__`; generate once inside the call wrapper with runtime context. `hasattr`/`dir()` on dynamic modules become free.
- **Owned event loop over monkeypatched host loop.** `asyncio.run` per explore() call; inside a running loop, run the exploration in a dedicated thread instead of `nest_asyncio.apply()` mutating the host. `nest_asyncio` can then be dropped from dependencies (added in plan 001 as the minimal fix).
- **Candidate execution in a bounded executor.** One `ThreadPoolExecutor` path for test/benchmark/fitness callables with per-candidate timeout and `BaseException` capture; timeouts and `SystemExit` recorded as candidate failures.
- **EvolutionResult wraps, doesn't replace.** The returned object stays callable (delegates to the winner) and proxies `__name__`/`__doc__`/`__wishful_source__`/`__wishful_evolution__` via `__getattr__` (not copy, so chained `evolve(evolve(fn))` sees current source); sets `__wrapped__` for `inspect.signature()`. **No `accept()` method ships** — spec-003 Open Decision 1 (auto-cache vs require-accept) is unresolved, so a no-op would let callers form false beliefs that later become silent behavior changes; adding `accept()` later is non-breaking, shipping a no-op now is a trap.
- **The shared compile-exec seam is the one real abstraction.** `compile_and_exec` (it compiles AND executes — naming matters for the casefile hook) has two consumers today (explorer, evolver), so it earns its place; its design leaves room for deferred casefile writes since those must not run inside the import lock. The speculative `registry_path()` stub is cut (see R13) — seams whose consumer shape is an open decision pay twice, not once.

---

## Implementation Units

### U1. Dynamic-mode economics and module integrity

- **Goal:** One generation per dynamic call; regeneration never corrupts module identity.
- **Requirements:** R1, R2
- **Dependencies:** none
- **Files:** `src/wishful/core/loader.py`, `tests/test_import_hook.py`, `tests/test_namespaces.py`
- **Approach:** remove the eager `_regenerate_for_proxy` generation from `__getattribute__` (generate inside `_call_with_runtime` only); preserve `__name__`/`__spec__`/`__loader__`/`__file__` across `clear_first` re-execs by snapshotting dunders and swapping the namespace atomically. Removing the eager regen forces an explicit decision the eager path papered over — pin and test all three: (a) calling a name absent from import-time generation must still generate-and-call (the dynamic-mode promise); (b) what `hasattr`/`dir` return for never-generated names, documented as intentional; (c) non-callable dynamic attributes (constants the eager regen used to materialize) — pick generate-on-access, import-time snapshot, or `AttributeError`. Update `tests/test_namespaces.py:93` which currently asserts `>= 4` generations (the bug); the post-fix invariant is 3 (1 import + 2 call-time).
- **Test scenarios:** generation-call counter shows exactly 1 call for `mod.fn(args)` after import; calling a never-generated name generates-and-calls; `hasattr(dynamic_mod, "x")` costs 0 calls and its return value matches the documented contract; non-callable attribute access behaves per the chosen semantics; `importlib.reload(static_mod)` works after a regeneration; `mod.__name__` intact after `__getattr__`-triggered regen; concurrent attribute access during regen sees either old or new namespace, never empty (best-effort lock test).
- **Verification:** review reproduction (3 generations for import+call) shows 2 (import + call) or fewer.

### U2. explore/evolve robustness

- **Goal:** Search loops that cannot destroy winners, hang, or kill the host.
- **Requirements:** R3, R4, R5, R6
- **Dependencies:** U1
- **Files:** `src/wishful/explore/explorer.py`, `src/wishful/explore/progress.py`, `src/wishful/explore/variant.py`, `src/wishful/evolve/evolver.py`, `tests/test_explore.py`, `tests/test_evolve.py`, `pyproject.toml`
- **Approach:** winner caching merges the winning function into an existing cached module (replace the symbol, keep siblings); `_ensure_symbols` recovery regenerates only missing symbols, never `delete_cached` on a module containing an explore winner; candidate callables run in a bounded executor with `shutdown(wait=False)` (CPython cannot cancel a running thread — a `while True` candidate is recorded failed at the timeout and the loop continues, but the thread runs to process exit; document this limit), catching `BaseException` to record `SystemExit`/timeout as failure; replace `_cached_loop`/atexit/nest_asyncio with `asyncio.run` + dedicated-thread fallback inside running loops. **The cached-loop existed to work around litellm's LoggingWorker breaking under per-call `asyncio.run` (explorer.py:30) — verify against litellm 1.88.x (plan-001 bump) before deleting it; if the problem persists, the conservative owned-loop design is one persistent loop in a dedicated background thread, never the host's.** `nest_asyncio` was a provisional dep added in plan 001 — its removal here is a net `pyproject.toml` deletion; coordinate with the plan-001 lock change. `VariantResult.error_message` stores full text (truncate only in the Rich renderer); `verbose` default `sys.stdout.isatty()`; `WISHFUL_EXPLORE_SAVE_RESULTS` env override.
- **Test scenarios:** explore winner for one symbol leaves a second cached symbol intact; recovery after winner-overwrite keeps the winner; candidate with `while True` → recorded failed at the timeout, run completes; candidate calling `sys.exit()` → recorded failed, host alive; explore() called from within `asyncio.run(...)` context completes (thread fallback); `ExplorationError.failures[n]` contains the full exception text; non-TTY stdout → no ANSI output by default.
- **Verification:** review cascade reproduction fails to reproduce; no `nest_asyncio` import remains.

### U3. Security depth

- **Goal:** Close the confirmed-but-deferred attack surfaces.
- **Requirements:** R7, R8
- **Dependencies:** none
- **Files:** `src/wishful/cache/manager.py`, `src/wishful/core/discovery.py`, `src/wishful/llm/client.py`, `src/wishful/llm/prompts.py`, `src/wishful/__init__.py`, `src/wishful/__main__.py`, `tests/test_cache.py`, `tests/test_safety.py`, `tests/test_llm.py`
- **Approach:** `module_path()` rejects names containing path separators or `..` and asserts the resolved path is within `cache_dir` (applies to `regenerate`, `reimport`, CLI `regen`); discovery context is wrapped in explicit untrusted-data delimiters in prompts and size-capped; debug logging redacts prompt/context bodies behind a separate `WISHFUL_LOG_PROMPTS=1` opt-in; add a poisoned-cache test corpus (bypass payloads planted in `.wishful/` must be rejected at load).
- **Test scenarios:** `regenerate("wishful.static.../../etc/passwd")` → `ValueError`, no filesystem touch; CLI `regen` with traversal name exits 1; prompt assembly wraps context in delimiters and truncates oversized context at the cap; `debug=True` without the opt-in logs metadata but not prompt bodies; planted `__import__('os')` cache file refuses to load.
- **Verification:** traversal and poisoned-cache reproductions fail.

### U4. Architecture seams for spec 003

- **Goal:** The active-import/casefile work lands on prepared ground.
- **Requirements:** R9, R10, R11, R12, R13, R14
- **Dependencies:** U2
- **Files:** `src/wishful/core/execution.py` (new), `src/wishful/explore/explorer.py`, `src/wishful/evolve/evolver.py`, `src/wishful/evolve/history.py`, `src/wishful/evolve/__init__.py`, `src/wishful/core/discovery.py`, `src/wishful/config.py`, `src/wishful/__init__.py`, `src/wishful/cache/manager.py`, `src/wishful/core/loader.py`, `tests/conftest.py`, `tests/test_evolve.py`, `tests/test_config.py`, `tests/test_discovery.py`
- **Approach:** extract `compile_and_exec(source, name, *, filename)` (compiles AND executes — it is the casefile hook point) into `core/execution.py` and use it from both explorer (`_compile_source`) and evolver (`_compile_function`), deleting the duplicates; designed so casefile writes can be deferred outside the import lock; introduce `EvolutionResult` proxying `__name__`/`__doc__`/`__wishful_source__`/`__wishful_evolution__` via `__getattr__` and setting `__wrapped__` (no `accept()` method — see KTD); `__wishful_evolution__` gets a `schema_version`ed TypedDict; move `context_radius` into Settings (configure/reset/env) with `set_context_radius()` delegating; pass registered-type context into explore's generation calls; mark the explore CSV writer as legacy pending the evidence layout; `configure()` under a `threading.Lock`; clear the type registry in the conftest autouse fixture; replace `_resolve_generate_module_code` with an injectable `MagicLoader.generate_fn` attribute.
- **Test scenarios:** explorer and evolver both route through the shared helper (one compile path, asserted via monkeypatch); `EvolutionResult` is callable and `result.fn(...) == result(...)`; `evolve(evolve(fn))` completes and `inspect.signature(result)` matches the winner; `__wishful_source__`/`__wishful_evolution__` proxy to current source after re-evolution; `configure(context_radius=6)` affects discovery and `reset_defaults()` restores it; explore prompt for a registered type contains the type schema; parallel `configure()` calls from 8 threads leave settings consistent; two tests registering the same type name don't bleed into each other.
- **Verification:** the structural seam is in place — `core/execution.py` exists, `explorer._compile_source` and `evolver._compile_function` are deleted in favor of `compile_and_exec`, and the helper signature admits a deferred-write callback (even if unused now). The seam is reviewed against the active-artifact direction in `docs/specs/003-wishful-code-search-workbench/concept-plan.md` (casefile + maintained-import sections), not a named slice.

### U5. Example coverage additions

- **Goal:** Every public feature teachable from `examples/`.
- **Requirements:** R15
- **Dependencies:** plan 001 shipped (CLI `--json`, review TTY behavior, precedence)
- **Files:** `examples/12_explore.py`, `examples/14_evolve.py`, `examples/15_cli_and_config.py` (new), `examples/16_safety_and_review.py` (new), `examples/09_context_shenanigans.py`, `examples/11_logging.py`, `README.md`
- **Approach:** extend 12 with `return_all=True`; extend 14 with `keep_history`/`history_limit` and an `EvolutionError` try/except mirroring 12's pattern; new 15: CLI commands incl. `--json` plus `configure(model/temperature/max_tokens)` and `reset_defaults()`; new 16: `SecurityError` catch, `allow_unsafe` explanation, `review=True` walkthrough (TTY-gated); give 09 a docstring and section comments; expand 11 to demonstrate `debug`, `log_level`, `log_to_file` distinctly; update the README examples tree to list all files.
- **Test scenarios:** all examples run green under `WISHFUL_FAKE_LLM=1` (CI-checkable); new examples join the release smoke sweep.
- **Verification:** feature-to-example matrix from the review artifact has no uncovered public feature.

### U6. Residual test debt and paper cuts

- **Goal:** Close the review's remaining confirmed gaps.
- **Requirements:** R16, R17
- **Dependencies:** none
- **Files:** `tests/test_types.py`, `tests/test_import_hook.py`, `tests/test_cache.py`, `tests/test_evolve.py`, `tests/test_discovery.py`, `src/wishful/core/finder.py`, `src/wishful/config.py`, `src/wishful/explore/explorer.py`, `pyproject.toml`
- **Approach:** add the #62 test bundle (registry v1-shim and TypedDict-vs-dataclass discrimination, `install()` idempotence, `_ensure_symbols` missing-symbol error, `delete_cached`/`has_cached`/snapshot-path helpers, evolve arg-validation ValueErrors, discovery Windows path normalization); reject depth>1 wish names in `find_spec` with a clear error before any LLM call; resolve `cache_dir` to absolute at configure time; scope the coroutine-warning filter to wishful's own call sites; bump mypy floor to `>=2.1` and fix anything it surfaces.
- **Test scenarios:** as enumerated per item above — each gap becomes at least one named test; `import wishful.static.a.b` raises `ImportError` mentioning nesting with zero generation calls; `os.chdir` mid-run keeps cache operations on the original directory.
- **Verification:** coverage on `explore/`, `evolve/`, `safety/`, `types/` ≥85%; `uv run mypy src/wishful` clean on mypy 2.x.

### U7. Orphan-finding cleanup

- **Goal:** Close the review findings neither plan otherwise owns.
- **Requirements:** R10 (extends), plus review #44, #48
- **Dependencies:** U4
- **Files:** `src/wishful/explore/variant.py`, `src/wishful/evolve/mutation.py`, `src/wishful/evolve/evolver.py`, `tests/test_explore.py`, `tests/test_evolve.py`, `tests/test_cache.py`
- **Approach:** (#44) make `__wishful_source__` unconditional on explore-returned functions (`fn.__wishful_source__ = metadata.source_code or ""`) so the documented attribute is never absent; (#48) resolve the evolve-sync vs explore-async LLM-path divergence — route `evolver`'s mutation through the same path the shared seam (U4) exposes, or explicitly document the sync path as acceptable until async evolve lands; add the cross-process cache-race test the review named (two writers, atomic-write property holds) rather than leaving that testing gap silently uncovered.
- **Test scenarios:** every explore-returned function has a string `__wishful_source__`; evolve and explore reach the LLM through one decided path (asserted via monkeypatch) or the divergence is documented with a test pinning current behavior; concurrent writers to the same cache path never produce a torn read.
- **Verification:** review findings #44, #48 and the cross-process-race testing gap each map to a passing test or a recorded deferral.

---

## Scope Boundaries

**Deferred for later:** the spec-003 implementation itself (active-import registry, casefiles, `report_failure()`, proof-gated repair, Codex runtime) — this plan only plants its seams; out-of-process sandboxing; async evolve.

**Outside this plan's identity:** new product surfaces (app-level wishes, dashboards, marketplaces) per STRATEGY.md's not-working-on list.

---

## Risks & Dependencies

- **Depends on plan 001 landing first** — several units build on its outcomes (timeout plumbing, hardened validator, namespaced cache). Sequencing is plan-level, not unit-level.
- **Event-loop redesign (U2) touches subtle async behavior**: mitigated by the Jupyter-simulation tests and the existing explore suite; the dedicated-thread fallback is the conservative design.
- **EvolutionResult introduces a new return type**: callable-wrapper design keeps old code working; the dunder attributes remain until spec 003 formalizes the contract.

---

## Sources & Research

- Origin review: `docs/reviews/2026-06-11-code-review.md` (P2/P3 tables, residual risks, testing gaps; full per-reviewer evidence in the run artifact)
- Spec-003 concept (the seams' consumer): `docs/specs/003-wishful-code-search-workbench/concept-plan.md`
- Strategy anchor: `STRATEGY.md` (maintained-imports track; not-working-on list)
- Feature-to-example matrix: example-coverage reviewer artifact from the review run
