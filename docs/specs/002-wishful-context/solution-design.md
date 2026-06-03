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
The implementation should target all live generation surfaces:

- `evolve()` in `src/wishful/evolve/evolver.py` and `src/wishful/evolve/mutation.py`
- `explore()` in `src/wishful/explore/explorer.py`
- static/dynamic import generation in `src/wishful/core/loader.py`

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

- file: src/wishful/explore/explorer.py
  relevance: HIGH
  why: "String-path generation surface that should include registered context"

- file: src/wishful/core/loader.py
  relevance: HIGH
  why: "Static/dynamic import generation surface that merges discovered import context with registered context"

- file: src/wishful/config.py
  relevance: HIGH
  why: "Settings and environment-variable control surface"

- file: src/wishful/cache/manager.py
  relevance: MEDIUM
  why: "Static cache policy and optional context-fingerprint metadata"

- file: AGENTS.md
  relevance: MEDIUM
  why: "Live repo instructions and architecture doc to update; this repo has no CLAUDE.md"
```

### Implementation Boundaries

- **Must Preserve**: Existing `@wishful.type` behavior, public `evolve()` API, public `explore()` API, and static cache-first behavior by default
- **Can Modify**: `config.py`, `explore/explorer.py`, `core/loader.py`, `evolve/*`, and cache metadata helpers
- **Must Not Touch**: static/dynamic namespace routing semantics, safety validation policy, or the core litellm client contract

### Project Commands

```bash
# Testing
uv run pytest tests/test_context.py -v          # Context tests
uv run pytest tests/test_evolve.py -v           # Verify evolve still works
uv run pytest tests/test_explore.py -v          # Verify explore context integration
uv run pytest tests/test_import_hook.py -v      # Verify static/dynamic generation
uv run pytest tests/test_namespaces.py -v       # Verify dynamic namespace behavior
uv run pytest tests/test_config.py -v           # Verify context settings
uv run pytest tests/ -v                          # Full suite

# Type checking
uv run mypy src/wishful/context/ src/wishful/evolve/

# Validation
uv run python -c "from wishful import context; print('OK')"
```

---

## Solution Strategy

- **Architecture Pattern**: Mirror `@wishful.type` exactly
- **Integration Approach**: Build one context-formatting helper and call it from evolve, explore, and static/dynamic import generation
- **Justification**: Proven pattern, predictable for users, minimal new concepts

---

## Building Block View

### Components

```mermaid
graph LR
    User[Developer] -->|decorates| Context[@wishful.context]
    Context -->|registers| Registry[ContextRegistry]
    Evolve[evolve/mutation.py] -->|looks up| Registry
    Explore[explore/explorer.py] -->|looks up| Registry
    Loader[core/loader.py] -->|looks up| Registry
    Registry -->|returns| Sources[Context Sources]
    Sources -->|included in| LLMPrompt[LLM Prompt]
```

### Directory Map

```
src/wishful/
├── context/                    # NEW MODULE
│   ├── __init__.py            # NEW: Public exports
│   ├── registry.py            # NEW: ContextRegistry + decorator
│   └── formatting.py          # NEW: prompt block builder + target expansion
├── config.py                  # MODIFY: context settings + env vars
├── __init__.py                # MODIFY: Add context exports
├── cache/
│   └── manager.py             # MODIFY: optional static context fingerprint metadata
├── core/
│   └── loader.py              # MODIFY: merge registered context into import generation
├── explore/
│   └── explorer.py            # MODIFY: include context in variant generation
└── evolve/
    ├── evolver.py             # MODIFY: Pass original target function to mutation
    └── mutation.py            # MODIFY: Integrate context lookup
tests/
├── test_context.py            # NEW: Unit tests
├── test_evolve.py             # MODIFY: Context integration tests
├── test_explore.py            # MODIFY: Explore context tests
├── test_import_hook.py        # MODIFY: Static import context tests
├── test_namespaces.py         # MODIFY: Dynamic context tests if needed
└── test_config.py             # MODIFY: Context setting tests
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

@dataclass
class ContextLookupOptions:
    """Resolved settings for prompt context lookup."""
    enabled: bool
    surfaces: tuple[str, ...]
    lookup: Literal["exact", "exact_then_module"]
    static_cache_policy: Literal["cache_first", "invalidate_on_change", "ignore"]
    max_entries: int
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

def build_context_block(
    targets: list[Any],
    *,
    surface: Literal["evolve", "explore", "static", "dynamic"],
    base_context: str | None = None,
) -> str | None:
    """Merge discovered context and registered context into one prompt block."""
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

#### Evolve

```
1. `evolve()` calls `mutate_with_llm(target_function=sort, ...)`
2. `mutate_with_llm()` passes `target_function` to `_build_evolution_context()`
3. `_build_evolution_context()` calls `build_context_block([sort], surface="evolve")`
4. Context is included under `ADDITIONAL CONTEXT`
```

#### Explore

```
1. `explore("wishful.static.text.extract_emails", ...)` splits module and function
2. Explorer builds target keys:
   - exact: `"wishful.static.text.extract_emails"`
   - module fallback when enabled: `"wishful.static.text"`
3. Explorer passes the merged context string to `agenerate_module_code(...)`
4. Test and benchmark callables remain execution-only unless explicitly registered
5. Winner caching remains unchanged unless static cache settings opt into context fingerprints
```

#### Static/Dynamic Imports

```
1. Loader calls `discover(fullname)` and receives import-site context plus requested symbols
2. Loader builds registered-context targets:
   - module target: `fullname`
   - exact function targets: `f"{fullname}.{symbol}"` for each requested symbol
3. Loader merges registered context with `ImportContext.context`
4. Static mode:
   - default `cache_first`: existing cache wins
   - `invalidate_on_change`: context fingerprint can invalidate stale cache
   - `ignore`: static import generation skips registered context
5. Dynamic mode regenerates every time, so registered context is included on every generation by default
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

Generated import targets should use their public import paths:

- exact function context: `"wishful.static.text.extract_emails"`
- module-level context: `"wishful.static.text"`
- dynamic equivalents: `"wishful.dynamic.text.extract_emails"` and `"wishful.dynamic.text"`

Static and dynamic are mode-specific by default. Users who want shared context
can register one provider for both targets with `for_=[...]`.

### Context Settings

Add these fields to `Settings`, `configure(...)`, and `reset_defaults()`:

| Setting | Env var | Default | Meaning |
|---------|---------|---------|---------|
| `context_enabled: bool` | `WISHFUL_CONTEXT` | `True` | Master switch for registered context |
| `context_surfaces: tuple[str, ...]` | `WISHFUL_CONTEXT_SURFACES` | `("evolve", "explore", "static", "dynamic")` | Surfaces that receive registered context |
| `context_lookup: str` | `WISHFUL_CONTEXT_LOOKUP` | `"exact_then_module"` | Include exact target only, or exact plus module fallback |
| `context_static_cache_policy: str` | `WISHFUL_CONTEXT_STATIC_CACHE_POLICY` | `"cache_first"` | Static cache behavior for context changes |
| `context_max_entries: int` | `WISHFUL_CONTEXT_MAX_ENTRIES` | `8` | Max registered context entries per prompt |

Allowed values:

- `context_lookup`: `"exact"`, `"exact_then_module"`
- `context_static_cache_policy`: `"cache_first"`, `"invalidate_on_change"`, `"ignore"`

Static cache policy semantics:

- `"cache_first"`: existing static cache wins; registered context affects only cache misses and explicit regeneration.
- `"invalidate_on_change"`: static cache stores a context fingerprint and regenerates when the fingerprint changes.
- `"ignore"`: static imports do not include registered context, even when context is enabled elsewhere.

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

- [x] **ADR-5**: Context applies to all generation surfaces in 002
  - Rationale: Context is a cross-cutting prompt primitive, not an evolve-only feature
  - Trade-offs: More tests and settings are required to keep cache behavior explicit
  - User confirmed: ✅ (2026-06-03 refresh)

- [x] **ADR-6**: Static imports stay cache-first by default
  - Rationale: `wishful.static.*` means cached and consistent; context should not cause surprise regeneration by default
  - Trade-offs: Users must opt into `invalidate_on_change` or call `regenerate()` when changing context for existing static cache files
  - User confirmed: ✅ (2026-06-03 refresh)

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
        from wishful.context import build_context_block
        registered_context = build_context_block(
            [target_function],
            surface="evolve",
        )
        if registered_context:
            parts.append(registered_context)
```

`evolve()` should pass the original function `fn` as `target_function`, not the
compiled candidate. The developer attached context to the target being evolved,
and that target stays stable while candidates change.

---

## Integration with explore()

In `_generate_and_evaluate_async()`, build context once per variant generation
from the `module_name` and `function_name` that `explore()` already parses:

```python
target = f"{module_name}.{function_name}"
context = build_context_block([target], surface="explore")
source = await asyncio.wait_for(
    agenerate_module_code(module_name, [function_name], context),
    timeout=timeout,
)
```

`test` and `benchmark` functions should not be automatically embedded into the
prompt. If users want those definitions visible to the LLM, they should register
them explicitly:

```python
@wishful.context(for_="wishful.static.text.extract_emails")
def email_extraction_context():
    """Must pass fixture-based tests and preserve input order."""
    ...
```

---

## Integration with static/dynamic imports

In `MagicLoader._generate_and_cache()`, merge registered context into the
discovered context before calling `generate_module_code(...)`.

```python
registered_context = build_context_block(
    [self.fullname, *[f"{self.fullname}.{name}" for name in functions]],
    surface=self.mode,
    base_context=context.context,
)

source = gen_fn(
    self.fullname,
    functions,
    registered_context,
    type_schemas=context.type_schemas,
    function_output_types=context.function_output_types,
    mode=self.mode,
)
```

Static mode must check the cache before generating when
`context_static_cache_policy="cache_first"`. For `invalidate_on_change`, add a
small metadata sidecar or equivalent cache helper that stores the context
fingerprint for the cached module. Dynamic mode does not need fingerprinting
because it already regenerates.

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

Scenario: Explore includes registered context
  Given context registered for "wishful.static.text.extract_emails"
  When explore generates variants for that path
  Then agenerate_module_code receives the registered context block

Scenario: Static import preserves cache-first behavior
  Given cached source exists for wishful.static.text
  And new context is registered for wishful.static.text.extract_emails
  When context_static_cache_policy is cache_first
  Then the cached source is used without regeneration

Scenario: Dynamic import includes registered context every time
  Given context registered for wishful.dynamic.text.extract_emails
  When dynamic import generation runs
  Then the registered context block is included in each generation
```

### Test Coverage Requirements

- Registry: register, get_for, clear, key resolution
- Decorator: with function, with string, with list
- Source extraction: functions, classes, with/without docstrings
- Evolve integration: `evolve()` passes the original target function to mutation
- Explore integration: context appears in variant-generation prompt
- Static integration: context merges with import-site context on cache miss or configured invalidation
- Dynamic integration: context merges with runtime/import-site context on every regeneration
- Settings: global enable, surface selection, lookup mode, static cache policy, max entries

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/wishful/context/__init__.py` | CREATE | Public exports |
| `src/wishful/context/registry.py` | CREATE | ContextRegistry + decorator |
| `src/wishful/context/formatting.py` | CREATE | Target expansion and prompt block formatting |
| `src/wishful/config.py` | MODIFY | Context settings and env vars |
| `src/wishful/__init__.py` | MODIFY | Add `context, get_context_for` |
| `src/wishful/explore/explorer.py` | MODIFY | Include context in variant generation |
| `src/wishful/core/loader.py` | MODIFY | Include context in static/dynamic generation |
| `src/wishful/cache/manager.py` | MODIFY | Optional context fingerprint metadata for static cache |
| `src/wishful/evolve/mutation.py` | MODIFY | Add `target_function` param to `mutate_with_llm()` and `_build_evolution_context()` |
| `src/wishful/evolve/evolver.py` | MODIFY | Pass the original `fn` into `mutate_with_llm(target_function=fn)` |
| `tests/test_context.py` | CREATE | Unit tests |
| `tests/test_evolve.py` | MODIFY | Cover context prompt integration from the public evolve loop |
| `tests/test_explore.py` | MODIFY | Cover explore prompt context |
| `tests/test_import_hook.py` | MODIFY | Cover static prompt context and cache-first policy |
| `tests/test_namespaces.py` | MODIFY | Cover dynamic prompt context |
| `tests/test_config.py` | MODIFY | Cover context settings |
