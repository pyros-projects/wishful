# Implementation Plan: wishful.evolve

## Validation Checklist

- [x] All specification file paths are correct and exist
- [x] Context priming section is complete
- [x] All implementation phases are defined
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Dependencies between phases are clear (no circular dependencies)
- [x] Parallel work is properly tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection `[activity: type]`
- [x] Every phase references relevant design sections
- [x] Every test references design acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup
- [x] A developer could follow this plan independently

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate
2. **During Implementation**: Reference specific design sections in each task
3. **After Each Task**: Run Specification Compliance checks
4. **Phase Completion**: Verify all specification requirements are met

### Deviation Protocol

If implementation cannot follow specification exactly:
1. Document the deviation and reason
2. Get approval before proceeding
3. Update design docs if the deviation is an improvement
4. Never deviate without documentation

## Metadata Reference

- `[parallel: true]` - Tasks that can run concurrently
- `[component: component-name]` - For multi-component features
- `[ref: document/section; lines: 1, 2-3]` - Links to specifications, patterns, or interfaces and (if applicable) line(s)
- `[activity: type]` - Activity hint for specialist agent selection

---

## Context Priming

*GATE: You MUST fully read all files mentioned in this section before starting any implementation.*

**Design Documentation**:

- `docs/specs/001-wishful-evolve/implementation-plan.md` - this implementation plan
- `docs/specs/002-wishful-context/product-requirements.md` - planned context layer
- `docs/specs/002-wishful-context/solution-design.md` - context integration point for evolve prompts
- `docs/specs/003-wishful-code-search-workbench/concept-plan.md` - product direction for function lineage and evidence casefiles

**Key Design Decisions**:

1. **History-as-Context is CRITICAL** - This is what differentiates `evolve()` from `explore()`. The LLM receives full history of previous attempts with fitness scores, enabling informed mutations (AlphaEvolve paradigm).

2. **Parameters for History Control** - `keep_history: bool = True` and `history_limit: int = 10` control whether/how much history is passed to the LLM.

3. **Sync API with Async Internals** - Follow the `explore()` pattern: sync public API wrapping async internals for responsive progress updates.

4. **Reuse Existing Infrastructure** - Use `wishful.llm.client.generate_module_code()` for LLM calls, `wishful.safety.validator` for code validation.

5. **Rich Metadata** - Evolved functions get `__wishful_evolution__` (stats) and `__wishful_source__` (code) attributes.

**Implementation Context**:

- **Test command**: `uv run pytest tests/test_evolve.py -v`
- **Full test suite**: `uv run pytest tests/ -v`
- **Type checking**: `uv run mypy src/wishful/evolve/`
- **Example**: `uv run python examples/14_evolve.py`
- **Fake LLM mode**: `WISHFUL_FAKE_LLM=1 uv run pytest tests/test_evolve.py -v`

**Patterns to Follow**:
- `src/wishful/explore/` - Reference for async/sync pattern, progress display, variant handling
- `src/wishful/llm/client.py` - LLM client usage patterns
- `src/wishful/safety/validator.py` - Code validation pattern

---

## Implementation Phases

### Phase 1: Foundation - Exceptions and History Tracking

- [x] T1 Phase 1: Foundation Layer `[component: evolve-foundation]`

    - [x] T1.1 Prime Context
        - [x] T1.1.1 Read design for EvolutionError requirements
        - [x] T1.1.2 Read design for EvolutionHistory requirements
        - [x] T1.1.3 Review existing explore exceptions pattern `[ref: src/wishful/explore/exceptions.py]`

    - [x] T1.2 Write Tests `[activity: test-execution]`
        - [x] T1.2.1 Create `tests/test_evolve.py` with `TestEvolutionError` class
        - [x] T1.2.2 Add `TestEvolveMetadata` tests
        - [x] T1.2.3 Add `TestEvolveHistory` tests

    - [x] T1.3 Implement `[activity: domain-modeling]`
        - [x] T1.3.1 Create `src/wishful/evolve/exceptions.py` with EvolutionError
        - [x] T1.3.2 Create `src/wishful/evolve/history.py` with VariantRecord, GenerationRecord, EvolutionHistory
        - [x] T1.3.3 Implement `get_context_for_llm(limit)` method - THE KEY ALPHAEVOLVE MECHANISM

    - [x] T1.4 Validate `[activity: run-tests]`
        - [x] T1.4.1 Run `uv run pytest tests/test_evolve.py::TestEvolutionError -v`
        - [x] T1.4.2 Run `uv run pytest tests/test_evolve.py::TestEvolveMetadata -v`
        - [x] T1.4.3 Run `uv run pytest tests/test_evolve.py::TestEvolveHistory -v`

---

### Phase 2: Mutation Module - The AlphaEvolve Core

- [x] T2 Phase 2: LLM Mutation with History Context `[component: evolve-mutation]`

    - [x] T2.1 Prime Context
        - [x] T2.1.1 Read mutation module design
        - [x] T2.1.2 Study `_build_evolution_context()` function - formats history for LLM
        - [x] T2.1.3 Review existing LLM client usage `[ref: src/wishful/llm/client.py]`

    - [x] T2.2 Write Tests `[activity: test-execution]`
        - [x] T2.2.1 Add `TestBuildEvolutionContext` tests (7 tests)
        - [x] T2.2.2 Add `TestTruncateSource` tests (3 tests)
        - [x] T2.2.3 Add `TestGetFunctionSource` tests (3 tests)
        - [x] T2.2.4 Add `TestMutateWithLLM` tests (3 tests)

    - [x] T2.3 Implement `[activity: component-development]`
        - [x] T2.3.1 Create `src/wishful/evolve/mutation.py`
        - [x] T2.3.2 Implement `mutate_with_llm(source, mutation_prompt, function_name, history)`
        - [x] T2.3.3 Implement `_build_evolution_context()` with rich history formatting
        - [x] T2.3.4 Implement `_truncate_source()` utility
        - [x] T2.3.5 Implement `get_function_source()` utility

    - [x] T2.4 Validate `[activity: run-tests]`
        - [x] T2.4.1 Run `uv run pytest tests/test_evolve.py -v` - 33 tests passing
        - [x] T2.4.2 Run `uv run mypy src/wishful/evolve/` - No issues
        - [x] T2.4.3 Create tryout scripts: 05, 06, 07

---

### Phase 3: Core Evolver - The Evolution Loop

- [x] T3 Phase 3: Main evolve() Function `[component: evolve-core]`

    - [x] T3.1 Prime Context
        - [x] T3.1.1 Read live evolve and workbench specs
        - [x] T3.1.2 Study evolution loop with history context passing
        - [x] T3.1.3 Review explore() implementation pattern `[ref: src/wishful/explore/explorer.py]`

    - [x] T3.2 Write Tests `[activity: test-execution]`
        - [x] T3.2.1 Add `TestEvolveBasic` tests
        - [x] T3.2.2 Add `TestEvolveWithTest` tests
        - [x] T3.2.3 Add public import integration tests

    - [x] T3.3 Implement `[activity: component-development]`
        - [x] T3.3.1 Create `src/wishful/evolve/evolver.py`
        - [x] T3.3.2 Implement `evolve()` with `keep_history` and `history_limit`
        - [x] T3.3.3 Implement evolution loop with history context passing to mutation
        - [x] T3.3.4 Implement `_compile_function()` helper

    - [x] T3.4 Validate `[activity: run-tests]`
        - [x] T3.4.1 Run `uv run pytest tests/test_evolve.py::TestEvolveBasic -q`
        - [x] T3.4.2 Run `uv run pytest tests/test_evolve.py::TestEvolveWithTest -q`
        - [x] T3.4.3 Run `uv run pytest tests/test_evolve.py -q`

---

### Phase 4: Public API and Integration

- [x] T4 Phase 4: Public API Integration `[component: evolve-api]`

    - [x] T4.1 Prime Context
        - [x] T4.1.1 Read public API requirements from this plan
        - [x] T4.1.2 Read integration requirements from this plan
        - [x] T4.1.3 Review existing wishful `__init__.py` exports `[ref: src/wishful/__init__.py]`

    - [x] T4.2 Write Tests `[activity: test-execution]`
        - [x] T4.2.1 Add `TestEvolveIntegration` tests
        - [x] T4.2.2 Add import tests for public API

    - [x] T4.3 Implement `[activity: component-development]`
        - [x] T4.3.1 Create `src/wishful/evolve/__init__.py` with exports
        - [x] T4.3.2 Update `src/wishful/__init__.py` to export `evolve` and `EvolutionError`

    - [x] T4.4 Validate `[activity: run-tests]`
        - [x] T4.4.1 Run `uv run pytest tests/test_evolve.py::TestEvolveIntegration -q`
        - [x] T4.4.2 Test import: `from wishful import evolve, EvolutionError`

---

### Phase 5: Example and Documentation

- [x] T5 Phase 5: Example and Final Polish `[component: evolve-docs]`

    - [x] T5.1 Prime Context
        - [x] T5.1.1 Read existing example patterns
        - [x] T5.1.2 Review existing examples pattern `[ref: examples/]`

    - [x] T5.2 Create Example `[activity: component-development]`
        - [x] T5.2.1 Create `examples/14_evolve.py`
        - [x] T5.2.2 Test example with fake LLM: `WISHFUL_FAKE_LLM=1 uv run python examples/14_evolve.py`

    - [x] T5.3 Validate `[activity: run-tests]`
        - [x] T5.3.1 Run full test suite: `uv run pytest tests/test_evolve.py -q`
        - [x] T5.3.2 Check coverage: `uv run pytest tests/test_evolve.py --cov=src/wishful/evolve --cov-report=term-missing`
        - [x] T5.3.3 Type check: `uv run mypy src/wishful/evolve/`

---

### Phase 6: Integration & End-to-End Validation

- [x] T6 Final Validation

    - [x] T6.1 All unit tests passing: `uv run pytest tests/test_evolve.py -q`
    - [x] T6.2 Integration with existing wishful features verified
    - [x] T6.3 Example runs successfully with fake LLM
    - [x] T6.4 Test coverage ≥90% for new code
    - [x] T6.5 Type hints complete, mypy passes
    - [x] T6.6 Docstrings complete for all public APIs
    - [x] T6.7 Full test suite still passes: `uv run pytest --cov=wishful tests/`
    - [x] T6.8 `from wishful import evolve, EvolutionError` works
    - [x] T6.9 Definition of Done checklist verified against this plan

---

## Definition of Done

From the design specification:

- [x] All tests in `test_evolve.py` pass (25+ tests)
- [x] Coverage for new code is ≥90%
- [x] `wishful.evolve` is importable from main package
- [x] History context is properly passed to LLM (the AlphaEvolve innovation)
- [x] Works with `WISHFUL_FAKE_LLM=1`
- [x] Documentation strings are complete
- [x] Example file demonstrates basic usage
- [x] Type hints complete, `mypy` passes

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM not using history context | Rich prompt formatting, clear instructions in `_build_evolution_context()` |
| History too long for context | `history_limit` parameter, truncated source in `_truncate_source()` |
| Infinite loops in fitness | `timeout_per_variant` parameter |
| Memory from many generations | Only keep top N variants via `history_limit` |
| Flaky tests | All tests use monkeypatched mutations (deterministic) |

---

## References

- [AlphaEvolve Blog Post](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) — Google DeepMind
- [AlphaEvolve Paper](https://arxiv.org/abs/2506.13131) — arXiv
- [OpenEvolve](https://huggingface.co/blog/codelion/openevolve) — Open source implementation
- Current design direction: `docs/specs/003-wishful-code-search-workbench/concept-plan.md`
- Context follow-up: `docs/specs/002-wishful-context/implementation-plan.md`
