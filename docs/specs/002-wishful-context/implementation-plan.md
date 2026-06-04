# Implementation Plan: wishful.context

## Validation Checklist

- [x] All specification file paths are correct and exist
- [x] Context priming section is complete
- [x] All implementation phases are defined
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Dependencies between phases are clear
- [x] Activity hints provided for specialist selection
- [x] Every phase references relevant SDD sections
- [x] Project commands match actual project setup
- [x] A developer could follow this plan independently

---

## Context Priming

*GATE: Read all files before starting implementation.*

**Current Status (2026-06-03 refresh)**:
- `wishful.evolve()` is implemented and exported.
- `wishful.context` is still unimplemented.
- 002 should finish with registered context available to `evolve()`,
  `explore()`, and `wishful.static.*` / `wishful.dynamic.*` imports.
- This repo uses `AGENTS.md` as the live agent architecture/instructions file;
  there is no `CLAUDE.md`.
- Always run project Python commands through `uv run`.

**Specification**:
- `docs/specs/002-wishful-context/product-requirements.md` - PRD
- `docs/specs/002-wishful-context/solution-design.md` - SDD

**Reference Implementation**:
- `src/wishful/types/registry.py` - Pattern to mirror exactly
- `src/wishful/types/__init__.py` - Export pattern
- `src/wishful/evolve/evolver.py` - Public evolve loop and mutation call site
- `src/wishful/evolve/mutation.py` - Prompt context builder to extend
- `src/wishful/explore/explorer.py` - String-path variant generation
- `src/wishful/core/loader.py` - Static/dynamic generation
- `src/wishful/config.py` - Settings and environment variables
- `src/wishful/cache/manager.py` - Static cache behavior

**Key Design Decisions**:
1. Mirror `@wishful.type` pattern exactly
2. Use `for_=` parameter name
3. Global registry only (no scopes)
4. List targets register the same provider for each target; priority for a target is registration order
5. Registered context applies to evolve, explore, static, and dynamic by default
6. Static imports stay cache-first by default; context-change invalidation is opt-in

**Commands**:
```bash
uv run pytest tests/test_context.py -v    # Context tests
uv run pytest tests/test_evolve.py -v     # Verify evolve still works
uv run pytest tests/test_explore.py -v    # Verify explore context integration
uv run pytest tests/test_import_hook.py -v # Verify static import behavior
uv run pytest tests/test_namespaces.py -v # Verify dynamic behavior
uv run pytest tests/test_config.py -v     # Verify settings
uv run mypy src/wishful/context/ src/wishful/evolve/ # Type check
uv run python -c "from wishful import context, get_context_for; print('OK')"
```

---

## Implementation Phases

### Phase 1: Context Registry Foundation

- [ ] T1 Phase 1: Registry and Decorator `[component: context]`

    - [ ] T1.1 Prime Context
        - [ ] T1.1.1 Read `src/wishful/types/registry.py` for pattern `[ref: SDD; lines: 22-35]`
        - [ ] T1.1.2 Read SDD Data Models section `[ref: SDD; lines: 95-114]`

    - [ ] T1.2 Write Tests `[activity: test-execution]`
        - [ ] T1.2.1 Create `tests/test_context.py` with `TestContextRegistry` class
        - [ ] T1.2.2 Test: `test_register_with_function_reference`
        - [ ] T1.2.3 Test: `test_register_with_string_path`
        - [ ] T1.2.4 Test: `test_register_with_list_targets`
        - [ ] T1.2.5 Test: `test_get_context_returns_sources`
        - [ ] T1.2.6 Test: `test_get_context_empty_for_unknown`
        - [ ] T1.2.7 Test: `test_clear_registry`
        - [ ] T1.2.8 Test: `test_multiple_contexts_same_target`
        - [ ] T1.2.9 Test: `test_docstring_extraction`
        - [ ] T1.2.10 Test: `test_rejects_callable_instance_target_without_stable_key`

    - [ ] T1.3 Implement `[activity: component-development]`
        - [ ] T1.3.1 Create `src/wishful/context/__init__.py` with exports
        - [ ] T1.3.2 Create `src/wishful/context/registry.py` with:
            - [ ] `ContextEntry` dataclass
            - [ ] `ContextRegistry` class
            - [ ] `_registry` global instance
            - [ ] `context(for_=)` decorator
            - [ ] `get_context_for(target)` function
            - [ ] `clear_context_registry()` function
        - [ ] T1.3.3 Create `src/wishful/context/formatting.py` with:
            - [ ] `build_context_block(targets, surface, base_context=None)`
            - [ ] target expansion for exact vs module fallback
            - [ ] max-entry limiting
            - [ ] surface enable/disable checks

    - [ ] T1.4 Validate `[activity: run-tests]`
        - [ ] T1.4.1 Run `uv run pytest tests/test_context.py -v`
        - [ ] T1.4.2 Run `uv run mypy src/wishful/context/`
        - [ ] T1.4.3 Verify import: `uv run python -c "from wishful.context import context, get_context_for"`

---

### Phase 2: Public API and Settings

- [ ] T2 Phase 2: Wishful Package Integration and Settings `[component: wishful]`

    - [ ] T2.1 Prime Context
        - [ ] T2.1.1 Read `src/wishful/__init__.py` for export pattern
        - [ ] T2.1.2 Read `src/wishful/config.py` for settings pattern

    - [ ] T2.2 Write Tests `[activity: test-execution]`
        - [ ] T2.2.1 Test: `test_context_importable_from_wishful`
        - [ ] T2.2.2 Test: `test_get_context_for_importable_from_wishful`
        - [ ] T2.2.3 Test: context settings default values
        - [ ] T2.2.4 Test: `configure()` updates context settings
        - [ ] T2.2.5 Test: environment variables populate context settings
        - [ ] T2.2.6 Test: `reset_defaults()` restores context settings

    - [ ] T2.3 Implement `[activity: component-development]`
        - [ ] T2.3.1 Modify `src/wishful/__init__.py` to export `context`, `get_context_for`
        - [ ] T2.3.2 Add settings:
            - [ ] `context_enabled: bool = True`
            - [ ] `context_surfaces: tuple[str, ...] = ("evolve", "explore", "static", "dynamic")`
            - [ ] `context_lookup: str = "exact_then_module"`
            - [ ] `context_static_cache_policy: str = "cache_first"`
            - [ ] `context_max_entries: int = 8`
        - [ ] T2.3.3 Add env vars:
            - [ ] `WISHFUL_CONTEXT`
            - [ ] `WISHFUL_CONTEXT_SURFACES`
            - [ ] `WISHFUL_CONTEXT_LOOKUP`
            - [ ] `WISHFUL_CONTEXT_STATIC_CACHE_POLICY`
            - [ ] `WISHFUL_CONTEXT_MAX_ENTRIES`
        - [ ] T2.3.4 Update `configure()`, `Settings.copy()`, and `reset_defaults()`

    - [ ] T2.4 Validate `[activity: run-tests]`
        - [ ] T2.4.1 Run `uv run python -c "from wishful import context, get_context_for; print('OK')"`
        - [ ] T2.4.2 Run `uv run pytest tests/test_config.py -v`
        - [ ] T2.4.3 Run full test suite: `uv run pytest tests/ -v`

---

### Phase 3: Evolve Integration

- [ ] T3 Phase 3: Integration with evolve module `[component: evolve]`

    - [ ] T3.1 Prime Context
        - [ ] T3.1.1 Read `src/wishful/evolve/mutation.py` current implementation
        - [ ] T3.1.2 Read `src/wishful/evolve/evolver.py` current implementation
        - [ ] T3.1.3 Read SDD Integration section

    - [ ] T3.2 Write Tests `[activity: test-execution]`
        - [ ] T3.2.1 Test: `test_build_evolution_context_includes_registered_context`
        - [ ] T3.2.2 Test: `test_build_evolution_context_no_context_registered`
        - [ ] T3.2.3 Test: `test_context_docstring_included_in_prompt`
        - [ ] T3.2.4 Test: public `evolve()` passes the original target function into mutation context lookup

    - [ ] T3.3 Implement `[activity: component-development]`
        - [ ] T3.3.1 Add `target_function: Callable | None = None` param to `_build_evolution_context()`
        - [ ] T3.3.2 Add context lookup and formatting logic
        - [ ] T3.3.3 Add `target_function: Callable | None = None` param to `mutate_with_llm()`
        - [ ] T3.3.4 Update `mutate_with_llm()` to pass target function to `_build_evolution_context()`
        - [ ] T3.3.5 Update `evolve()` to call `mutate_with_llm(..., target_function=fn)` with the original target function

    - [ ] T3.4 Validate `[activity: run-tests]`
        - [ ] T3.4.1 Run `uv run pytest tests/test_evolve.py -v`
        - [ ] T3.4.2 Run `uv run pytest tests/test_context.py -v`
        - [ ] T3.4.3 Run full suite: `uv run pytest tests/ -v`

---

### Phase 4: Explore Integration

- [ ] T4 Phase 4: Explore Integration `[component: explore]`

    - [ ] T4.1 Prime Context
        - [ ] T4.1.1 Read `src/wishful/explore/explorer.py`
        - [ ] T4.1.2 Read SDD Explore Integration section

    - [ ] T4.2 Write Tests `[activity: test-execution]`
        - [ ] T4.2.1 Test: `explore()` includes exact target registered context
        - [ ] T4.2.2 Test: module-level context is included when `context_lookup="exact_then_module"`
        - [ ] T4.2.3 Test: module-level context is excluded when `context_lookup="exact"`
        - [ ] T4.2.4 Test: explore skips context when `"explore"` is not in `context_surfaces`
        - [ ] T4.2.5 Test: `test` and `benchmark` callables are not automatically embedded

    - [ ] T4.3 Implement `[activity: component-development]`
        - [ ] T4.3.1 Build exact explore target from `module_name` and `function_name`
        - [ ] T4.3.2 Pass `build_context_block(..., surface="explore")` result to `agenerate_module_code(...)`
        - [ ] T4.3.3 Preserve winner caching behavior

    - [ ] T4.4 Validate `[activity: run-tests]`
        - [ ] T4.4.1 Run `uv run pytest tests/test_explore.py -v`
        - [ ] T4.4.2 Run `uv run pytest tests/test_context.py -v`

---

### Phase 5: Static/Dynamic Import Integration

- [ ] T5 Phase 5: Static/Dynamic Import Integration `[component: import-hook]`

    - [ ] T5.1 Prime Context
        - [ ] T5.1.1 Read `src/wishful/core/loader.py`
        - [ ] T5.1.2 Read `src/wishful/core/discovery.py`
        - [ ] T5.1.3 Read `src/wishful/cache/manager.py`
        - [ ] T5.1.4 Read SDD Static/Dynamic Integration section

    - [ ] T5.2 Write Tests `[activity: test-execution]`
        - [ ] T5.2.1 Test: static cache miss includes registered exact function context
        - [ ] T5.2.2 Test: static cache miss merges registered context with discovered import-site context
        - [ ] T5.2.3 Test: existing static cache wins when `context_static_cache_policy="cache_first"`
        - [ ] T5.2.4 Test: static cache regenerates on context fingerprint change when `context_static_cache_policy="invalidate_on_change"`
        - [ ] T5.2.5 Test: static skips registered context when `context_static_cache_policy="ignore"`
        - [ ] T5.2.6 Test: dynamic generation includes registered context on each regeneration
        - [ ] T5.2.7 Test: multiple requested symbols include symbol-specific context
        - [ ] T5.2.8 Test: module-level context is included/excluded according to `context_lookup`

    - [ ] T5.3 Implement `[activity: component-development]`
        - [ ] T5.3.1 Add loader helper to build context targets from `fullname` and requested functions
        - [ ] T5.3.2 Merge registered context into `context.context` before `generate_module_code(...)`
        - [ ] T5.3.3 Preserve static `cache_first` path before generation
        - [ ] T5.3.4 Add optional context fingerprint metadata for `invalidate_on_change`
        - [ ] T5.3.5 Ensure dynamic mode includes registered context on proxy/runtime regeneration

    - [ ] T5.4 Validate `[activity: run-tests]`
        - [ ] T5.4.1 Run `uv run pytest tests/test_import_hook.py -v`
        - [ ] T5.4.2 Run `uv run pytest tests/test_namespaces.py -v`
        - [ ] T5.4.3 Run `uv run pytest tests/test_context.py -v`

---

### Phase 6: Documentation & Spec Updates

- [ ] T6 Phase 6: Documentation, Examples, and Spec Updates `[component: docs]`

    - [ ] T6.1 Update Evolve Implementation Plan
        - [ ] T6.1.1 Add note about `@wishful.context` integration in `docs/specs/001-wishful-evolve/implementation-plan.md`
        - [ ] T6.1.2 Update Phase 3 (Core Evolver) to pass `target_function` to mutation

    - [ ] T6.2 Update Workbench Direction Docs
        - [ ] T6.2.1 Add context integration section to `docs/specs/003-wishful-code-search-workbench/concept-plan.md`
        - [ ] T6.2.2 Document which tricky behavior is configurable

    - [ ] T6.3 Update AGENTS.md
        - [ ] T6.3.1 Add `wishful.context` to architecture section
        - [ ] T6.3.2 Update repository layout and test list if needed

    - [ ] T6.4 Create Examples
        - [ ] T6.4.1 Create `examples/15_context_basic.py`
        - [ ] T6.4.2 Create `examples/16_context_with_evolve.py`
        - [ ] T6.4.3 Create `examples/17_context_with_explore.py`
        - [ ] T6.4.4 Create `examples/18_context_with_static_import.py`
        - [ ] T6.4.5 Document context examples and settings in `README.md`

---

### Phase 7: Final Validation

- [ ] T7 Integration & End-to-End Validation

    - [ ] T7.1 All unit tests passing: `uv run pytest tests/test_context.py -v`
    - [ ] T7.2 All evolve tests passing: `uv run pytest tests/test_evolve.py -v`
    - [ ] T7.3 All explore tests passing: `uv run pytest tests/test_explore.py -v`
    - [ ] T7.4 Import-hook tests passing: `uv run pytest tests/test_import_hook.py tests/test_namespaces.py -v`
    - [ ] T7.5 Full test suite passing: `uv run pytest tests/ -v`
    - [ ] T7.6 Type checking passes: `uv run mypy src/wishful/context/ src/wishful/evolve/`
    - [ ] T7.7 Import verification: `uv run python -c "from wishful import context, get_context_for; print('OK')"`
    - [ ] T7.8 Test coverage ≥90% for new code
    - [ ] T7.9 Tryout scripts run successfully
    - [ ] T7.10 PRD acceptance criteria verified:
        - [ ] `@wishful.context(for_=target)` works
        - [ ] Supports function references
        - [ ] Supports string paths
        - [ ] Supports list of targets
        - [ ] `get_context_for()` returns source + docstring
        - [ ] Integrates with `_build_evolution_context()`
        - [ ] Integrates with `explore()`
        - [ ] Integrates with static import generation
        - [ ] Integrates with dynamic import generation
        - [ ] Context settings work through `configure()` and env vars

---

## Definition of Done

- [ ] All tests pass (≥15 new tests)
- [ ] Test coverage ≥90% for `src/wishful/context/`
- [ ] `wishful.context` importable from main package
- [ ] Works with evolve's `_build_evolution_context()`
- [ ] Works with explore variant generation
- [ ] Works with static and dynamic import generation
- [ ] Static cache remains cache-first by default
- [ ] Context settings documented and tested
- [ ] Documentation updated (AGENTS.md, README, evolve/workbench docs)
- [ ] Tryout scripts demonstrate usage
- [ ] Type hints complete, mypy passes

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Circular import with evolve | Lazy import in `_build_evolution_context()` |
| Source extraction fails | Store a descriptive stub string with provider name/module so prompts remain readable |
| Target resolution ambiguous | Clear error messages, documentation |
| Context bloats prompts | `context_max_entries` and exact-only lookup setting |
| Static cache surprises users | Default `cache_first`, explicit `invalidate_on_change` opt-in |
| Context changes do not affect existing cached static modules | Document default clearly and offer `regenerate()` or `invalidate_on_change` |
