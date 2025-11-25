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

### Problem Statement
When wishful generates or evolves code, the LLM lacks crucial context:
- **evolve()**: LLM sees fitness *scores* but not *what's being measured*
- **explore()**: LLM generates variants without knowing constraints or goals
- **static**: Generation happens without domain-specific hints or examples

Without this context, the LLM is essentially guessing what "good" means.

**Evidence**: During evolve() Phase 2 implementation, we discovered that `_build_evolution_context()` passes history with scores (90, 55, 25) but never explains WHY those scores differ. The LLM must reverse-engineer the fitness function from code patterns.

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
  - [ ] Works with functions, classes, and any callable

#### Feature 2: Multiple Targets
- **User Story:** As a developer, I want one context to serve multiple functions so that I don't repeat myself.
- **Acceptance Criteria:**
  - [ ] `@wishful.context(for_=[sort, search])` registers for both targets
  - [ ] Order in list determines priority (first = highest)

#### Feature 3: Context Registry
- **User Story:** As wishful internals, I need to look up all context for a given target.
- **Acceptance Criteria:**
  - [ ] `get_context_for(target)` returns list of context sources
  - [ ] Returns source code of decorated items
  - [ ] Respects priority ordering
  - [ ] Returns empty list if no context registered

#### Feature 4: Integration Point
- **User Story:** As wishful.evolve (and future features), I need to include context in LLM prompts.
- **Acceptance Criteria:**
  - [ ] Context can be retrieved and formatted for LLM consumption
  - [ ] Works with `_build_evolution_context()` in evolve module
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
- Rule 4: String targets resolved at lookup time, not registration

**Edge Cases:**
- Target doesn't exist yet (string path) → Register anyway, resolve later
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
- Must follow existing wishful patterns (`@wishful.type`, `@wishful.static`)
- Must not require changes to existing user code
- Must work with Python 3.12+

### Assumptions
- Global registry is sufficient for initial release
- Users will provide context as functions or classes (not arbitrary objects)
- Source code extraction via `inspect.getsource()` or `__wishful_source__` is reliable

---

## Open Questions

- [x] Naming: `for_=` vs `target=` → **Decision: `for_=`** (most natural English)
- [x] Multiple targets: Yes, via list
- [x] Priority: Order in list
- [x] Scope: Global only for now
