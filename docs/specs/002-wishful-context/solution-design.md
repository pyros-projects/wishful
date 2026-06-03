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
```

### Implementation Boundaries

- **Must Preserve**: Existing `@wishful.type` behavior, `evolve()` API
- **Can Modify**: `_build_evolution_context()` to include registered context
- **Must Not Touch**: Core wishful generation logic

### Project Commands

```bash
# Testing
uv run pytest tests/test_context.py -v          # Context tests
uv run pytest tests/test_evolve.py -v           # Verify evolve still works
uv run pytest tests/ -v                          # Full suite

# Type checking
uv run mypy src/wishful/context/

# Validation
python -c "from wishful import context; print('OK')"
```

---

## Solution Strategy

- **Architecture Pattern**: Mirror `@wishful.type` exactly
- **Integration Approach**: Add optional context lookup to LLM prompt building
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
    └── mutation.py            # MODIFY: Integrate context lookup
tests/
└── test_context.py            # NEW: Unit tests
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
3. Registry resolves target to key: "mymodule.sort"
4. Registry extracts source + docstring from provider
5. Registry stores ContextEntry in _contexts["mymodule.sort"]
```

### Lookup Flow

```
1. evolve() calls _build_evolution_context(target_function=sort)
2. _build_evolution_context calls get_context_for(sort)
3. Registry resolves sort → "mymodule.sort"
4. Registry returns list of ContextEntry dicts
5. Context included in LLM prompt under "ADDITIONAL CONTEXT"
```

### Target Resolution Logic

```python
def _resolve_key(self, target: Any) -> str:
    if isinstance(target, str):
        return target  # Already a string path
    elif callable(target):
        return f"{target.__module__}.{target.__qualname__}"
    else:
        raise TypeError(f"Target must be callable or string, got {type(target)}")
```

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

- [x] **ADR-4**: List targets = register for each with priority order
  - Rationale: DRY for shared context, priority by position
  - Trade-offs: Implicit priority might surprise some users
  - User confirmed: ✅ (from earlier discussion)

---

## Integration with evolve()

### Changes to mutation.py

```python
# In _build_evolution_context(), add after history section:

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
- Integration: context appears in evolve prompt

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/wishful/context/__init__.py` | CREATE | Public exports |
| `src/wishful/context/registry.py` | CREATE | ContextRegistry + decorator |
| `src/wishful/__init__.py` | MODIFY | Add `context, get_context_for` |
| `src/wishful/evolve/mutation.py` | MODIFY | Add `target_function` param |
| `tests/test_context.py` | CREATE | Unit tests |
