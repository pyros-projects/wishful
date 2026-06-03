# Product Requirements Document: wishful.context

## Validation Checklist

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Problem is validated by evidence (not assumptions)
- [x] Context → Problem → Solution flow makes sense
- [x] Every feature has testable acceptance criteria
- [x] No technical implementation details included

---

## Product Overview

### Vision
Enable developers to declaratively attach contextual information (fitness functions, constraints, examples, hints) to wishful-generated functions, making LLM generation smarter and more targeted.

### Current Status
This spec was refreshed on 2026-06-03 after the public `wishful.evolve()` loop merged.
`wishful.context` is still unimplemented. The next implementation should target
the current evolve spine in `src/wishful/evolve/evolver.py` and
`src/wishful/evolve/mutation.py`.

### Problem Statement
When wishful generates or evolves code, the LLM lacks crucial context:
- **evolve()**: LLM sees fitness *scores* but not *what's being measured*
- **explore()**: LLM generates variants without knowing constraints or goals
- **static**: Generation happens without domain-specific hints or examples

Without this context, the LLM is essentially guessing what "good" means.

**Evidence**: The merged evolve spine passes prior attempts and fitness scores to
`_build_evolution_context()`, but it still does not include the fitness function,
constraints, examples, or acceptance rationale. The LLM must reverse-engineer why
one variant scored better than another from source patterns alone.

### Value Proposition
`@wishful.context` provides a declarative, composable way to give the LLM exactly the context it needs - making generation smarter without changing the core wishful API.

---

## Feature Requirements

### Must Have Features

#### Feature 1: Context Decorator
- **User Story:** As a developer, I want to attach context to a wishful function so that the LLM understands what I'm optimizing for.
- **Acceptance Criteria:**
  - [ ] `@wishful.context(for_=target)` decorator registers context
  - [ ] Supports function references: `@wishful.context(for_=sort)`
  - [ ] Supports string paths: `@wishful.context(for_="module.func")`
  - [ ] Works with functions and classes that have stable module-qualified names

#### Feature 2: Multiple Targets
- **User Story:** As a developer, I want one context to serve multiple functions so that I don't repeat myself.
- **Acceptance Criteria:**
  - [ ] `@wishful.context(for_=[sort, search])` registers for both targets
  - [ ] Each target keeps context entries in registration order

#### Feature 3: Context Registry
- **User Story:** As wishful internals, I need to look up all context for a given target.
- **Acceptance Criteria:**
  - [ ] `get_context_for(target)` returns list of context sources
  - [ ] Returns source code of decorated items
  - [ ] Respects registration-order priority
  - [ ] Returns empty list if no context registered

#### Feature 4: Integration Point
- **User Story:** As wishful.evolve (and future features), I need to include context in LLM prompts.
- **Acceptance Criteria:**
  - [ ] Context can be retrieved and formatted for LLM consumption
  - [ ] Works with `_build_evolution_context()` in evolve module
  - [ ] `evolve()` passes the target function through to mutation so context lookup can use the original callable
  - [ ] Pattern matches existing `@wishful.type` infrastructure

### Should Have Features

#### Feature 5: Docstring Extraction
- **User Story:** As a developer, I want my context function's docstring to be included as human-readable explanation.
- **Acceptance Criteria:**
  - [ ] Docstrings are extracted and included in context
  - [ ] Source code AND docstring both available

### Won't Have (This Phase)

- **Scoped registries** - Start global only, scoped contexts for later
- **Context validation** - No runtime checking that context is "correct"
- **Auto-discovery** - No scanning modules for context, must be explicit
- **Priority override** - No way to re-order after registration
- **Direct `explore()` or static import integration** - The registry should be reusable, but this phase only wires context into `evolve()`
- **Callable-instance targets** - Function and class targets are supported first; arbitrary callable objects are out of scope until there is a clear stable-key rule

---

## Detailed Feature Specification

### Feature: Context Decorator + Registry

**User Flow:**
```python
# 1. Developer decorates context providers
@wishful.context(for_=sort)
def sorting_benchmark(fn) -> float:
    """Measures speed on large reversed arrays. Higher = faster."""
    ...

@wishful.context(for_=sort)
class SortingConstraints:
    """Edge cases that must be handled."""
    EMPTY = []
    DUPLICATES = [1, 1, 1]

# 2. Wishful internally looks up context
contexts = wishful.context.get_context_for(sort)
# Returns: [source of sorting_benchmark, source of SortingConstraints]

# 3. Context included in LLM prompt during generation/evolution
```

**Business Rules:**
- Rule 1: Context is registered at decoration time (import time)
- Rule 2: Multiple contexts for same target are allowed
- Rule 3: Order of registration = priority order
- Rule 4: String targets are stored as stable keys; callable lookup normalizes to the same key format

**Edge Cases:**
- Target doesn't exist yet (string path) → Register anyway; later callable lookup matches if it normalizes to the same path
- No context for target → Return empty list (not an error)
- Same context decorated twice → Register twice (user's choice)

---

## Success Criteria

| Criterion | Measurement |
|-----------|-------------|
| Works with evolve() | Context appears in LLM prompt during evolution |
| Pattern consistency | API feels like `@wishful.type` |
| No breaking changes | Existing wishful code unaffected |
| Test coverage | ≥90% for new code |

---

## Constraints and Assumptions

### Constraints
- Must follow existing wishful patterns (`@wishful.type`, `wishful.evolve`)
- Must not require changes to existing user code
- Must work with Python 3.12+

### Assumptions
- Global registry is sufficient for initial release
- Users will provide context providers as functions or classes (not arbitrary instances)
- Source code extraction via `inspect.getsource()` or `__wishful_source__` is reliable

---

## Open Questions

- [x] Naming: `for_=` vs `target=` → **Decision: `for_=`** (most natural English)
- [x] Multiple targets: Yes, via list
- [x] Priority: Registration order for contexts under the same target
- [x] Scope: Global only for now
