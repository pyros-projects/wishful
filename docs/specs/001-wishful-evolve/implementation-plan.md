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

- `.internal/wishful-research/pyglove/02-evolve-design.md` - Full design specification
  - AlphaEvolve research foundation (lines 7-40)
  - API specification with all parameters (lines 92-139)
  - History-as-context mechanism (lines 143-228)
  - Usage examples (lines 281-415)
  - Error handling (lines 509-525)

- `.internal/wishful-research/pyglove/02-evolve-implementation.md` - TDD implementation guide
  - File structure (lines 17-33)
  - Complete test suite (lines 37-585)
  - Implementation code for all modules (lines 589-1121)
  - Example file (lines 1185-1254)

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
- **Example**: `uv run python examples/13_evolve.py`
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
        - [x] T1.1.1 Read design for EvolutionError requirements `[ref: 02-evolve-implementation.md; lines: 591-617]`
        - [x] T1.1.2 Read design for EvolutionHistory requirements `[ref: 02-evolve-implementation.md; lines: 623-731]`
        - [x] T1.1.3 Review existing explore exceptions pattern `[ref: src/wishful/explore/exceptions.py]`

    - [x] T1.2 Write Tests `[activity: test-execution]`
        - [x] T1.2.1 Create `tests/test_evolve.py` with `TestEvolutionError` class `[ref: 02-evolve-implementation.md; lines: 508-531]`
        - [x] T1.2.2 Add `TestEvolveMetadata` tests `[ref: 02-evolve-implementation.md; lines: 375-418]`
        - [x] T1.2.3 Add `TestEvolveHistory` tests `[ref: 02-evolve-implementation.md; lines: 421-448]`

    - [x] T1.3 Implement `[activity: domain-modeling]`
        - [x] T1.3.1 Create `src/wishful/evolve/exceptions.py` with EvolutionError `[ref: 02-evolve-implementation.md; lines: 593-617]`
        - [x] T1.3.2 Create `src/wishful/evolve/history.py` with VariantRecord, GenerationRecord, EvolutionHistory `[ref: 02-evolve-implementation.md; lines: 625-731]`
        - [x] T1.3.3 Implement `get_context_for_llm(limit)` method - THE KEY ALPHAEVOLVE MECHANISM `[ref: 02-evolve-implementation.md; lines: 671-697]`

    - [x] T1.4 Validate `[activity: run-tests]`
        - [x] T1.4.1 Run `uv run pytest tests/test_evolve.py::TestEvolutionError -v`
        - [x] T1.4.2 Run `uv run pytest tests/test_evolve.py::TestEvolveMetadata -v`
        - [x] T1.4.3 Run `uv run pytest tests/test_evolve.py::TestEvolveHistory -v`

---

### Phase 2: Mutation Module - The AlphaEvolve Core

- [ ] T2 Phase 2: LLM Mutation with History Context `[component: evolve-mutation]`

    - [ ] T2.1 Prime Context
        - [ ] T2.1.1 Read mutation module design `[ref: 02-evolve-implementation.md; lines: 737-889]`
        - [ ] T2.1.2 Study `_build_evolution_context()` function - formats history for LLM `[ref: 02-evolve-implementation.md; lines: 784-862]`
        - [ ] T2.1.3 Review existing LLM client usage `[ref: src/wishful/llm/client.py]`

    - [ ] T2.2 Write Tests `[activity: test-execution]`
        - [ ] T2.2.1 Add `TestEvolveMutationPrompt` tests `[ref: 02-evolve-implementation.md; lines: 347-372]`
        - [ ] T2.2.2 Add `TestEvolveHistoryContext` tests (CRITICAL - the AlphaEvolve innovation) `[ref: 02-evolve-implementation.md; lines: 130-261]`
        - [ ] T2.2.3 Add `TestEvolveErrorCases` for mutation failures `[ref: 02-evolve-implementation.md; lines: 451-505]`

    - [ ] T2.3 Implement `[activity: component-development]`
        - [ ] T2.3.1 Create `src/wishful/evolve/mutation.py` `[ref: 02-evolve-implementation.md; lines: 741-889]`
        - [ ] T2.3.2 Implement `mutate_with_llm(source, mutation_prompt, function_name, history)` `[ref: 02-evolve-implementation.md; lines: 751-781]`
        - [ ] T2.3.3 Implement `_build_evolution_context()` with rich history formatting `[ref: 02-evolve-implementation.md; lines: 784-862]`
        - [ ] T2.3.4 Implement `get_function_source()` utility `[ref: 02-evolve-implementation.md; lines: 873-889]`

    - [ ] T2.4 Validate `[activity: run-tests]`
        - [ ] T2.4.1 Run `uv run pytest tests/test_evolve.py::TestEvolveMutationPrompt -v`
        - [ ] T2.4.2 Run `uv run pytest tests/test_evolve.py::TestEvolveHistoryContext -v`
        - [ ] T2.4.3 Run `uv run pytest tests/test_evolve.py::TestEvolveErrorCases -v`

---

### Phase 3: Core Evolver - The Evolution Loop

- [ ] T3 Phase 3: Main evolve() Function `[component: evolve-core]`

    - [ ] T3.1 Prime Context
        - [ ] T3.1.1 Read evolver design `[ref: 02-evolve-implementation.md; lines: 895-1121]`
        - [ ] T3.1.2 Study evolution loop with history context passing `[ref: 02-evolve-implementation.md; lines: 984-1081]`
        - [ ] T3.1.3 Review explore() implementation pattern `[ref: src/wishful/explore/explorer.py]`

    - [ ] T3.2 Write Tests `[activity: test-execution]`
        - [ ] T3.2.1 Add `TestEvolveBasic` tests `[ref: 02-evolve-implementation.md; lines: 52-127]`
        - [ ] T3.2.2 Add `TestEvolveWithTest` tests `[ref: 02-evolve-implementation.md; lines: 264-344]`
        - [ ] T3.2.3 Add `TestEvolveVerbose` tests `[ref: 02-evolve-implementation.md; lines: 534-558]`

    - [ ] T3.3 Implement `[activity: component-development]`
        - [ ] T3.3.1 Create `src/wishful/evolve/evolver.py` `[ref: 02-evolve-implementation.md; lines: 897-1121]`
        - [ ] T3.3.2 Implement `evolve()` with full parameter set including `keep_history` and `history_limit` `[ref: 02-evolve-implementation.md; lines: 909-950]`
        - [ ] T3.3.3 Implement evolution loop with history context passing to mutation `[ref: 02-evolve-implementation.md; lines: 984-1081]`
        - [ ] T3.3.4 Implement `_compile_function()` helper `[ref: 02-evolve-implementation.md; lines: 1109-1120]`

    - [ ] T3.4 Validate `[activity: run-tests]`
        - [ ] T3.4.1 Run `uv run pytest tests/test_evolve.py::TestEvolveBasic -v`
        - [ ] T3.4.2 Run `uv run pytest tests/test_evolve.py::TestEvolveWithTest -v`
        - [ ] T3.4.3 Run `uv run pytest tests/test_evolve.py::TestEvolveVerbose -v`

---

### Phase 4: Public API and Integration

- [ ] T4 Phase 4: Public API Integration `[component: evolve-api]`

    - [ ] T4.1 Prime Context
        - [ ] T4.1.1 Read public API design `[ref: 02-evolve-implementation.md; lines: 1127-1150]`
        - [ ] T4.1.2 Read integration requirements `[ref: 02-evolve-implementation.md; lines: 1154-1168]`
        - [ ] T4.1.3 Review existing wishful `__init__.py` exports `[ref: src/wishful/__init__.py]`

    - [ ] T4.2 Write Tests `[activity: test-execution]`
        - [ ] T4.2.1 Add `TestEvolveIntegration` tests `[ref: 02-evolve-implementation.md; lines: 561-584]`
        - [ ] T4.2.2 Add import tests for public API

    - [ ] T4.3 Implement `[activity: component-development]`
        - [ ] T4.3.1 Create `src/wishful/evolve/__init__.py` with exports `[ref: 02-evolve-implementation.md; lines: 1129-1150]`
        - [ ] T4.3.2 Update `src/wishful/__init__.py` to export `evolve` and `EvolutionError` `[ref: 02-evolve-implementation.md; lines: 1158-1168]`

    - [ ] T4.4 Validate `[activity: run-tests]`
        - [ ] T4.4.1 Run `uv run pytest tests/test_evolve.py::TestEvolveIntegration -v`
        - [ ] T4.4.2 Test import: `python -c "from wishful import evolve, EvolutionError; print('OK')"`

---

### Phase 5: Example and Documentation

- [ ] T5 Phase 5: Example and Final Polish `[component: evolve-docs]`

    - [ ] T5.1 Prime Context
        - [ ] T5.1.1 Read example file design `[ref: 02-evolve-implementation.md; lines: 1185-1254]`
        - [ ] T5.1.2 Review existing examples pattern `[ref: examples/]`

    - [ ] T5.2 Create Example `[activity: component-development]`
        - [ ] T5.2.1 Create `examples/13_evolve.py` `[ref: 02-evolve-implementation.md; lines: 1189-1254]`
        - [ ] T5.2.2 Test example with fake LLM: `WISHFUL_FAKE_LLM=1 uv run python examples/13_evolve.py`

    - [ ] T5.3 Validate `[activity: run-tests]`
        - [ ] T5.3.1 Run full test suite: `uv run pytest tests/test_evolve.py -v`
        - [ ] T5.3.2 Check coverage: `uv run pytest tests/test_evolve.py --cov=src/wishful/evolve --cov-report=term-missing`
        - [ ] T5.3.3 Type check: `uv run mypy src/wishful/evolve/`

---

### Phase 6: Integration & End-to-End Validation

- [ ] T6 Final Validation

    - [ ] T6.1 All unit tests passing: `uv run pytest tests/test_evolve.py -v`
    - [ ] T6.2 Integration with existing wishful features verified
    - [ ] T6.3 Example runs successfully with fake LLM
    - [ ] T6.4 Test coverage ≥90% for new code
    - [ ] T6.5 Type hints complete, mypy passes
    - [ ] T6.6 Docstrings complete for all public APIs
    - [ ] T6.7 Full test suite still passes: `uv run pytest tests/ -v`
    - [ ] T6.8 `from wishful import evolve, EvolutionError` works
    - [ ] T6.9 Definition of Done checklist from design doc verified `[ref: 02-evolve-implementation.md; lines: 1172-1183]`

---

## Definition of Done

From the design specification:

- [ ] All tests in `test_evolve.py` pass (25+ tests)
- [ ] Coverage for new code is ≥90%
- [ ] `wishful.evolve` is importable from main package
- [ ] History context is properly passed to LLM (the AlphaEvolve innovation)
- [ ] Works with `WISHFUL_FAKE_LLM=1`
- [ ] Documentation strings are complete
- [ ] Example file demonstrates basic usage
- [ ] Type hints complete, `mypy` passes

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
- Design Doc: `.internal/wishful-research/pyglove/02-evolve-design.md`
- Implementation Guide: `.internal/wishful-research/pyglove/02-evolve-implementation.md`
