# Solution Design Document: wishful.context

## Validation Checklist

- [x] All required sections are complete
- [x] Architecture pattern clearly stated
- [x] Every component has directory mapping
- [x] All architecture decisions confirmed
- [x] A developer could implement from this design

---

## Constraints

- **CON-1**: Must follow existing wishful patterns (`@wishful.type` in `src/wishful/types/`)
- **CON-2**: Python 3.12+, no external dependencies beyond existing
- **CON-3**: Must not break existing wishful API

## Implementation Context

### Current Status

This design was refreshed on 2026-06-03 after `wishful.evolve()` shipped.
The implementation should target the live public evolve loop in
`src/wishful/evolve/evolver.py`, where `evolve()` calls `mutate_with_llm(...)`,
and the live mutation context builder in `src/wishful/evolve/mutation.py`.

### Required Context Sources

```yaml
- file: src/wishful/types/registry.py
  relevance: CRITICAL
  why: "Pattern to mirror exactly - registry class, decorator, global instance"

- file: src/wishful/types/__init__.py
  relevance: HIGH
  why: "Export pattern to follow"

- file: src/wishful/evolve/mutation.py
  relevance: HIGH
  why: "Integration point - _build_evolution_context() will use context registry"

- file: src/wishful/evolve/evolver.py
  relevance: HIGH
  why: "Call site that must pass the original target function to mutate_with_llm"

- file: AGENTS.md
  relevance: MEDIUM
  why: "Live repo instructions and architecture doc to update; this repo has no CLAUDE.md"
```

### Implementation Boundaries

- **Must Preserve**: Existing `@wishful.type` behavior, `evolve()` API
- **Can Modify**: `mutate_with_llm()` and `_build_evolution_context()` to accept optional target context
- **Must Not Touch**: Import-hook generation behavior, cache behavior, or static/dynamic namespace semantics

### Project Commands

```bash
# Testing
uv run pytest tests/test_context.py -v          # Context tests
uv run pytest tests/test_evolve.py -v           # Verify evolve still works
uv run pytest tests/ -v                          # Full suite

# Type checking
uv run mypy src/wishful/context/

# Validation
uv run python -c "from wishful import context; print('OK')"
```

---

## Solution Strategy

- **Architecture Pattern**: Mirror `@wishful.type` exactly
- **Integration Approach**: Add optional context lookup to evolve's mutation prompt builder
- **Justification**: Proven pattern, predictable for users, minimal new concepts

---

## Building Block View

### Components

```mermaid
graph LR
    User[Developer] -->|decorates| Context[@wishful.context]
    Context -->|registers| Registry[ContextRegistry]
    Evolve[evolve/mutation.py] -->|looks up| Registry
    Registry -->|returns| Sources[Context Sources]
    Sources -->|included in| LLMPrompt[LLM Prompt]
```

### Directory Map

```
src/wishful/
├── context/                    # NEW MODULE
│   ├── __init__.py            # NEW: Public exports
│   └── registry.py            # NEW: ContextRegistry + decorator
├── __init__.py                # MODIFY: Add context exports
└── evolve/
    ├── evolver.py             # MODIFY: Pass original target function to mutation
    └── mutation.py            # MODIFY: Integrate context lookup
tests/
├── test_context.py            # NEW: Unit tests
└── test_evolve.py             # MODIFY: Context integration tests
```

### Data Models

```python
@dataclass
class ContextEntry:
    """Single context provider entry."""
    source: str              # Source code of provider
    docstring: str | None    # Extracted docstring
    provider: Any            # Reference to original (for debugging)

class ContextRegistry:
    """Global registry for context providers."""
    _contexts: dict[str, list[ContextEntry]]  # target_key -> entries

    def register(self, provider: Any, for_: Any) -> None: ...
    def get_for(self, target: Any) -> list[ContextEntry]: ...
    def clear(self) -> None: ...
    def _resolve_key(self, target: Any) -> str: ...
    def _extract_source(self, provider: Any) -> str: ...
```

### API Surface

```python
# Public API (from wishful.context)
def context(*, for_: Any) -> Callable:
    """Decorator to register context for a target."""

def get_context_for(target: Any) -> list[dict]:
    """Get all context entries for a target."""

def clear_context_registry() -> None:
    """Clear registry (for testing)."""
```

---

## Runtime View

### Registration Flow

```
1. Module imports → @wishful.context(for_=sort) executes
2. Decorator calls _registry.register(provider, for_=sort)
3. Registry normalizes target to key: "mymodule.sort"
4. Registry extracts source + docstring from provider
5. Registry stores ContextEntry in _contexts["mymodule.sort"]
```

### Lookup Flow

```
1. `evolve()` calls `mutate_with_llm(target_function=sort, ...)`
2. `mutate_with_llm()` passes `target_function` to `_build_evolution_context()`
3. `_build_evolution_context()` calls `get_context_for(sort)`
4. Registry normalizes `sort` → `"mymodule.sort"`
5. Registry returns list of context-entry dicts
6. Context is included in the LLM prompt under `ADDITIONAL CONTEXT`
```

### Target Resolution Logic

```python
def _resolve_key(self, target: Any) -> str:
    if isinstance(target, str):
        return target  # Already a stable key; no import resolution
    elif callable(target) and hasattr(target, "__module__") and hasattr(target, "__qualname__"):
        return f"{target.__module__}.{target.__qualname__}"
    else:
        raise TypeError(
            "Target must be a string path or a function/class with a stable "
            f"module-qualified name, got {type(target)}"
        )
```

String targets are not imported or resolved during registration. They are stored
as stable keys so code can register context for generated or not-yet-importable
targets. Later lookups by callable match when the callable normalizes to the
same module-qualified key.

---

## Architecture Decisions

- [x] **ADR-1**: Mirror @wishful.type pattern exactly
  - Rationale: Proven, consistent, less cognitive load for users
  - Trade-offs: Less flexibility, but simplicity wins
  - User confirmed: ✅ (from earlier discussion)

- [x] **ADR-2**: Use `for_=` parameter name
  - Rationale: Most natural English ("context for X")
  - Trade-offs: Underscore needed due to reserved word
  - User confirmed: ✅ (from earlier discussion)

- [x] **ADR-3**: Global registry only (no scopes)
  - Rationale: Keep simple, add scopes later if needed
  - Trade-offs: Can't have module-local contexts
  - User confirmed: ✅ (from earlier discussion)

- [x] **ADR-4**: List targets = register the same provider for each target
  - Rationale: DRY for shared context without duplicating decorators
  - Trade-offs: Priority is still per target and follows registration order
  - User confirmed: ✅ (from earlier discussion)

---

## Integration with evolve()

### Changes to mutation.py

```python
# In _build_evolution_context(), add after history section:

def mutate_with_llm(
    source: str,
    mutation_prompt: str,
    function_name: str,
    history: List[dict],
    target_function: Callable | None = None,  # NEW parameter
) -> str:
    context = _build_evolution_context(
        source,
        mutation_prompt,
        function_name,
        history,
        target_function=target_function,
    )
    ...


def _build_evolution_context(
    source: str,
    mutation_prompt: str,
    function_name: str,
    history: List[dict],
    target_function: Callable | None = None,  # NEW parameter
) -> str:
    ...
    # NEW: Include registered context
    if target_function:
        from wishful.context import get_context_for
        contexts = get_context_for(target_function)
        if contexts:
            parts.extend([
                "-" * 60,
                "ADDITIONAL CONTEXT (provided by developer):",
                "-" * 60,
                "",
            ])
            for ctx in contexts:
                if ctx.get("docstring"):
                    parts.append(f"# {ctx['docstring']}")
                parts.extend([
                    "```python",
                    ctx["source"],
                    "```",
                    "",
                ])
```

`evolve()` should pass the original function `fn` as `target_function`, not the
compiled candidate. The developer attached context to the target being evolved,
and that target stays stable while candidates change.

---

## Test Specifications

### Critical Test Scenarios

```gherkin
Scenario: Register context with function reference
  Given a function `sort` exists
  When developer decorates a fitness function with @wishful.context(for_=sort)
  Then get_context_for(sort) returns the fitness function's source

Scenario: Register context with string path
  Given no function exists yet
  When developer decorates with @wishful.context(for_="future.module.func")
  Then context is registered for that string key

Scenario: Multiple contexts for same target
  Given two contexts registered for `sort`
  When get_context_for(sort) is called
  Then both contexts returned in registration order

Scenario: No context registered
  When get_context_for(unknown_func) is called
  Then empty list returned (not an error)
```

### Test Coverage Requirements

- Registry: register, get_for, clear, key resolution
- Decorator: with function, with string, with list
- Source extraction: functions, classes, with/without docstrings
- Evolve integration: `evolve()` passes the original target function to mutation
- Integration: context appears in evolve prompt

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/wishful/context/__init__.py` | CREATE | Public exports |
| `src/wishful/context/registry.py` | CREATE | ContextRegistry + decorator |
| `src/wishful/__init__.py` | MODIFY | Add `context, get_context_for` |
| `src/wishful/evolve/mutation.py` | MODIFY | Add `target_function` param to `mutate_with_llm()` and `_build_evolution_context()` |
| `src/wishful/evolve/evolver.py` | MODIFY | Pass the original `fn` into `mutate_with_llm(target_function=fn)` |
| `tests/test_context.py` | CREATE | Unit tests |
| `tests/test_evolve.py` | MODIFY | Cover context prompt integration from the public evolve loop |
