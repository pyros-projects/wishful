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

**Key Design Decisions**:
1. Mirror `@wishful.type` pattern exactly
2. Use `for_=` parameter name
3. Global registry only (no scopes)
4. List targets register the same provider for each target; priority for a target is registration order

**Commands**:
```bash
uv run pytest tests/test_context.py -v    # Context tests
uv run pytest tests/test_evolve.py -v     # Verify evolve still works
uv run mypy src/wishful/context/          # Type check
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

    - [ ] T1.4 Validate `[activity: run-tests]`
        - [ ] T1.4.1 Run `uv run pytest tests/test_context.py -v`
        - [ ] T1.4.2 Run `uv run mypy src/wishful/context/`
        - [ ] T1.4.3 Verify import: `uv run python -c "from wishful.context import context, get_context_for"`

---

### Phase 2: Public API Export

- [ ] T2 Phase 2: Wishful Package Integration `[component: wishful]`

    - [ ] T2.1 Prime Context
        - [ ] T2.1.1 Read `src/wishful/__init__.py` for export pattern

    - [ ] T2.2 Write Tests `[activity: test-execution]`
        - [ ] T2.2.1 Test: `test_context_importable_from_wishful`
        - [ ] T2.2.2 Test: `test_get_context_for_importable_from_wishful`

    - [ ] T2.3 Implement `[activity: component-development]`
        - [ ] T2.3.1 Modify `src/wishful/__init__.py` to export `context`, `get_context_for`

    - [ ] T2.4 Validate `[activity: run-tests]`
        - [ ] T2.4.1 Run `uv run python -c "from wishful import context, get_context_for; print('OK')"`
        - [ ] T2.4.2 Run full test suite: `uv run pytest tests/ -v`

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

### Phase 4: Documentation & Spec Updates

- [ ] T4 Phase 4: Update 001-wishful-evolve Documentation `[component: docs]`

    - [ ] T4.1 Update Evolve Implementation Plan
        - [ ] T4.1.1 Add note about `@wishful.context` integration in `docs/specs/001-wishful-evolve/implementation-plan.md`
        - [ ] T4.1.2 Update Phase 3 (Core Evolver) to pass `target_function` to mutation

    - [ ] T4.2 Update Evolve Design Docs
        - [ ] T4.2.1 Add context integration section to `docs/specs/001-wishful-evolve/implementation-plan.md`
        - [ ] T4.2.2 Add context follow-up notes to `docs/specs/003-wishful-code-search-workbench/concept-plan.md`

    - [ ] T4.3 Update AGENTS.md
        - [ ] T4.3.1 Add `wishful.context` to architecture section
        - [ ] T4.3.2 Update repository layout and test list if needed

    - [ ] T4.4 Create Tryout Scripts
        - [ ] T4.4.1 Create `examples/15_context_basic.py`
        - [ ] T4.4.2 Create `examples/16_context_with_evolve.py`
        - [ ] T4.4.3 Document context examples in `README.md`

---

### Phase 5: Final Validation

- [ ] T5 Integration & End-to-End Validation

    - [ ] T5.1 All unit tests passing: `uv run pytest tests/test_context.py -v`
    - [ ] T5.2 All evolve tests passing: `uv run pytest tests/test_evolve.py -v`
    - [ ] T5.3 Full test suite passing: `uv run pytest tests/ -v`
    - [ ] T5.4 Type checking passes: `uv run mypy src/wishful/context/ src/wishful/evolve/`
    - [ ] T5.5 Import verification: `uv run python -c "from wishful import context, get_context_for; print('OK')"`
    - [ ] T5.6 Test coverage ≥90% for new code
    - [ ] T5.7 Tryout scripts run successfully
    - [ ] T5.8 PRD acceptance criteria verified:
        - [ ] `@wishful.context(for_=target)` works
        - [ ] Supports function references
        - [ ] Supports string paths
        - [ ] Supports list of targets
        - [ ] `get_context_for()` returns source + docstring
        - [ ] Integrates with `_build_evolution_context()`

---

## Definition of Done

- [ ] All tests pass (≥15 new tests)
- [ ] Test coverage ≥90% for `src/wishful/context/`
- [ ] `wishful.context` importable from main package
- [ ] Works with evolve's `_build_evolution_context()`
- [ ] Documentation updated (AGENTS.md, evolve docs)
- [ ] Tryout scripts demonstrate usage
- [ ] Type hints complete, mypy passes

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Circular import with evolve | Lazy import in `_build_evolution_context()` |
| Source extraction fails | Store a descriptive stub string with provider name/module so prompts remain readable |
| Target resolution ambiguous | Clear error messages, documentation |
