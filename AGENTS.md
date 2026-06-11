# AGENTS: wishful 🪄

This document is for future agents (human or AI) working on the `wishful` repository.  
Its goal is to let you start contributing immediately without a deep code dive.

If you only remember one thing: **this is a _uv‑managed_ project — always use `uv` (`uv run`, `uv add`, `uv lock`, etc.), never raw `pip` or `python` inside this repo.**

---

## Golden Rules

- **Always use `uv`:**
  - Run anything with the environment via `uv run …`.
  - Manage dependencies only via `uv add` / `uv add --dev` / `uv lock`.
  - Do **not** use `pip install`, `python -m pip`, or bare `python` for project tasks.
- **Python version:** the project targets **Python ≥ 3.12** (see `pyproject.toml`).
- **LLM access:** real generation uses `litellm` and environment variables; tests are designed to run **without network**.
- **Safety first:** generated code is statically checked; do not weaken safety rules without updating tests and documentation.
- **Tests are your contract:** before and after changes, run the relevant `pytest` suite via `uv`.
- **Test-Driven Development (TDD) Process:**
  1. **Before implementation:** Run all tests with coverage: `uv run pytest --cov=wishful tests/`
  2. **Design new tests:** Write tests for the new feature/fix before implementing
  3. **Implement:** Write the actual code to make tests pass
  4. **Verify:** Run tests again, fix issues until all green
  5. **Coverage gate:** Ensure new global coverage is not less than before

---

## Tooling & Environment (uv‑centric)

This repository is configured around [uv](https://docs.astral.sh/uv/). Treat `uv` as your only entry point.

### Install uv (once, outside the project)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Create / sync the environment

From the repo root:

```bash
uv sync
```

This reads `pyproject.toml` and `uv.lock`, creates a virtual env, and installs:

- Runtime deps: `litellm`, `rich`, `python-dotenv`, `pydantic`, `loguru`, `nest-asyncio`
- Dev deps: `pytest`, `pytest-cov`, `coverage`, `mypy`, `ruff`, `bandit`, `radon`

### Running commands (always via `uv run`)

- Python modules / scripts:

  ```bash
  uv run python examples/00_quick_start.py
  uv run python -m wishful inspect
  ```

- Tests:

  ```bash
  uv run pytest tests/ -v
  uv run pytest tests/test_import_hook.py -v
  ```

If you find yourself about to type `python …` or `pytest …`, prepend `uv run` instead.

### Managing dependencies (never use pip here)

- Add a runtime dependency:

  ```bash
  uv add some-package
  ```

- Add a dev‑only dependency:

  ```bash
  uv add --dev some-test-tool
  ```

- Upgrade locked versions:

  ```bash
  uv lock --upgrade
  ```

`uv` will keep `pyproject.toml` and `uv.lock` in sync. Do not edit the lock file by hand.

- **Docs site:** lives in `docs-site/`, built with Astro + Starlight. Use `npm install`, `npm run dev`, `npm run build` there. Keep using `uv` for all Python tasks.

---

## High‑Level Overview

**wishful** lets users write imports like:

```python
from wishful.static.text import extract_emails
```

and, on first import, an LLM generates the implementation on the fly. The generated module is cached as plain Python in a configurable directory (default `.wishful/`). Subsequent imports use the cache without calling the LLM again.

### Namespace Architecture (Important!)

The project uses **three distinct namespaces**:

1. **`wishful.static.*`** — Cached generation (default behavior)
   - Generated code is written to cache and reused on subsequent imports
   - Optimized for performance and consistency
   - Use for: utilities, parsers, validators, anything that doesn't need runtime context

2. **`wishful.dynamic.*`** — Runtime-context-aware generation
   - Regenerates on every import, capturing fresh runtime context each time
   - Never uses cache (always calls LLM)
   - Use for: creative content, context-sensitive functions, testing variations

3. **`wishful.*` (internal)** — Protected internal modules
   - Real package modules: `wishful.cache`, `wishful.config`, `wishful.types`, `wishful.core`, etc.
   - Cannot be overridden by code generation
   - Import these normally for internal API access

**Critical for tests and examples:** Always use `wishful.static.*` or `wishful.dynamic.*` for generated modules, never bare `wishful.*` (which would conflict with internal modules).

### Dynamic Import Mechanics (Critical!)

Understanding how `wishful.dynamic.*` imports work is essential for correct usage:

**How Dynamic Modules Work:**
- Dynamic modules use `DynamicProxyModule`, which wraps callable attributes
- Each **function call** triggers fresh regeneration with runtime context
- The `_call_with_runtime` method captures actual arguments and regenerates code based on them

**Correct Usage Patterns:**

```python
# ✓ CORRECT: Import the module, then call functions on it
import wishful.dynamic.jokes
print(wishful.dynamic.jokes.programming_joke())  # Regenerates!
print(wishful.dynamic.jokes.programming_joke())  # Regenerates again!

# ✓ ALSO CORRECT: Use wishful.reimport() for explicit control
jokes = wishful.reimport('wishful.dynamic.jokes')
print(jokes.programming_joke())  # Fresh generation

# ✗ WRONG: Importing individual functions binds them once
from wishful.dynamic.jokes import programming_joke
print(programming_joke())  # First call works
print(programming_joke())  # NO regeneration! Same function!
```

**Why the Anti-Pattern Fails:**
- `from wishful.dynamic.X import func` binds `func` to the local namespace **once**
- Subsequent calls to `func()` just execute the already-bound function object
- No regeneration occurs because Python doesn't re-execute the import statement

**When to Use `reimport()`:**
- Explicit control over when regeneration happens
- Useful in loops where you want fresh generation on each iteration
- Works with both `wishful.static.*` (bypasses cache) and `wishful.dynamic.*` (same as normal behavior)

**Key Takeaway:** For `wishful.dynamic.*`, always import the **module**, not individual functions.

---

Key properties:

- Uses a custom **import hook** (meta‑path finder + loader) with namespace routing.
- **Context‑aware**: forwards nearby comments/code lines to the LLM as hints.
- **Type-aware**: supports complex return types via `@wishful.type` decorator (see Type Registry section).
- **Safety‑checked**: generated code is parsed and checked for obviously dangerous constructs.
- **Cache‑backed**: generated modules live as `.py` files and can be edited or committed.

### Active Product Direction: Code Search Workbench

The current serious direction is not "one-shot helper generation." It is bounded
code search: target artifact + mutation space + fitness function + budget +
accept/rollback. Before extending `evolve`, `context`, CLI, demos, or the
dashboard, read:

- `docs/specs/001-wishful-evolve/implementation-plan.md`
- `docs/specs/002-wishful-context/implementation-plan.md`
- `docs/specs/003-wishful-code-search-workbench/concept-plan.md`

The key product primitive is "function with lineage": import address, current
source, context, variants, scores, failures, winner, evidence scope, and
accept/rollback state.

---

## Repository Layout

From the root:

- `docs/solutions/` — documented solutions to past problems (bugs, best practices, workflow patterns), organized by category with YAML frontmatter (`module`, `tags`, `problem_type`). Relevant when implementing or debugging in documented areas.
- `CONCEPTS.md` — shared domain vocabulary (entities, named processes, status concepts with project-specific meaning). Relevant when orienting to the codebase or discussing domain concepts.
- `pyproject.toml`  
  - Project metadata: name, version, description.
  - `requires-python = ">=3.12"`.
- Runtime deps: `litellm`, `rich`, `python-dotenv`, `pydantic`, `loguru`, `nest-asyncio`
- Dev deps under `[dependency-groups].dev`: `pytest`, `pytest-cov`, `coverage`, `mypy`, `ruff`, `bandit`, `radon`
  - Build system uses `uv_build` as backend.
  - Declares a `wishful` console script via `[project.scripts]` (`wishful = "wishful.__main__:main"`).

- `uv.lock`  
  - uv’s lockfile. Treat as generated; do not hand‑edit.

- `src/wishful/` – main package
  - `__init__.py`  
    - Public API (`__all__`): `configure`, `clear_cache`, `inspect_cache`, `regenerate`, `reimport`, `set_context_radius`, `settings`, `reset_defaults`, `WishfulError`, `SecurityError`, `GenerationError`, `ExplorationError`, `EvolutionError`, `explore`, `evolve`.
    - `wishful.type` (the type-registry decorator) is exposed as an attribute but **deliberately omitted from `__all__`** so `from wishful import *` does not shadow the builtin `type`.
    - `__version__` is derived from installed package metadata (`importlib.metadata.version`), not hardcoded; falls back to `"0.0.0+unknown"` in a source checkout.
    - Installs the import finder on import (`install_finder()`), so `import wishful` activates the magic.
  - `exceptions.py`  
    - `WishfulError` base exception; the more specific errors (`SecurityError`, `GenerationError`, `ExplorationError`, `EvolutionError`) derive from it.
  - `logging.py`  
    - loguru-based logging citizenship. File logging is opt-in (`WISHFUL_LOG_TO_FILE=1`); a bare `import wishful` creates no files.
  - `__main__.py`  
    - CLI entry point. Both the `wishful` console script and `python -m wishful` route here.
    - Provides `inspect`, `clear`, `regen` subcommands, all wired to cache and config; each accepts `--json`. Also supports `--version`.
    - Exit codes: `0` success, `1` runtime error, `2` usage error (argparse).
  - `config.py`  
    - Defines the `Settings` dataclass and the global `settings` instance.
    - Reads environment variables (e.g. `WISHFUL_MODEL`/`DEFAULT_MODEL`, `WISHFUL_CACHE_DIR`, `WISHFUL_REQUEST_TIMEOUT`, `WISHFUL_LOG_*`, other `WISHFUL_*` flags).
    - Model precedence: `WISHFUL_MODEL` wins over `DEFAULT_MODEL` (the wishful-specific var takes precedence; `DEFAULT_MODEL` is only the fallback). Built-in default is `"azure/gpt-4.1"`.
    - Provides `configure(**kwargs)` and `reset_defaults()` utilities.
  - `core/` – import mechanics
    - `__init__.py` – re‑exports `MagicFinder`, `MagicLoader`, `install`.
    - `finder.py` – `MagicFinder` (meta‑path finder) that intercepts `wishful.static.*` and `wishful.dynamic.*` imports, routes them to appropriate loaders, and protects internal `wishful.*` modules.
    - `loader.py` – `MagicLoader` and `MagicPackageLoader`:
      - Accepts `mode` parameter ("static" or "dynamic") to control caching behavior.
      - Handles cache lookup (static only), LLM generation, dynamic regeneration when requested symbols are missing, and dynamic `__getattr__` for on‑demand symbols.
  - `cache/` – cache management
    - `manager.py` – cache path computation, read/write, clear, list.
      - Strips `static`/`dynamic` namespace prefixes from cache paths so both use same cache file.
  - `llm/`
    - `client.py` – wraps `litellm` calls and exposes `generate_module_code`, `GenerationError`.
    - Accepts `type_schemas` and `function_output_types` for type-aware generation.
    - `_FAKE_MODE` via `WISHFUL_FAKE_LLM=1` returns deterministic stubs (no network).
    - `prompts.py` – prompt construction (`build_messages`) and `strip_code_fences`.
      - Formats type schemas and output types in system prompt for LLM.
  - `types/` – type registry system
    - `__init__.py` – exports `type` decorator and registry functions.
    - `registry.py` – `TypeRegistry` class for registering and serializing complex types.
      - Supports Pydantic models, dataclasses, TypedDict.
      - `@wishful.type` decorator for registering types and binding to function outputs.
      - Serializes type definitions to Python code for inclusion in LLM prompts.
  - `safety/`
    - `validator.py` – `validate_code(source, allow_unsafe)` plus `SecurityError`.
    - AST checks: forbidden imports (`os`, `subprocess`, `sys`, `importlib`, `builtins`, `ctypes`); forbidden calls (`eval`, `exec`, `compile`, `__import__`); `__builtins__`/`globals()`/`vars()` gadget access; `getattr` for forbidden attributes; write-mode or non-literal-mode `open()`; attribute calls on unbound `os`/`subprocess`/`sys`/`importlib`/`ctypes` (local bindings are tracked to avoid false positives). The same scan re-runs on cache load.
    - **Defense in depth, not a sandbox.** Generated code runs in-process; aliased/computed access can bypass a static scan (documented as `xfail` residuals in `tests/test_safety.py`). Keep validator coverage ≥90% and never weaken a rule without updating the negative/positive corpus and the README Safety Rails section.
  - `explore/` – multi-variant generation
    - `__init__.py` – exports `explore`, `ExplorationError`.
    - `explorer.py` – core `explore()` function for generating and selecting variants.
    - `variant.py` – `VariantMetadata` class and metadata wrapper.
    - `progress.py` – Rich Live progress display and CSV logging.
    - `exceptions.py` – `ExplorationError` exception.
  - `evolve/` – generational evolution of a function
    - `__init__.py` – exports `evolve`, `EvolutionError`.
    - `evolver.py` – core `evolve()` loop: scores variants, feeds prior attempts/scores/failures back into each mutation round.
    - `history.py` – evolution history tracking (per-generation summaries, attempted variants).
    - `mutation.py` – mutation-prompt construction for the next generation.
    - `exceptions.py` – `EvolutionError` exception.
  - `ui.py`
    - `spinner(message)` context manager using `rich` to show an optional spinner (controlled by `settings.spinner`).

- `tests/`
  - `conftest.py` – `reset_wishful` fixture:
    - Forces per‑test cache dir under `tmp_path`.
    - Disables spinner and interactive review.
    - Keeps safety ON by default (`allow_unsafe=False`); the few tests that need a bypass opt in via the `unsafe_settings` fixture. Wipes modules and cache between tests.
  - Individual test modules (326 tests total; prefer the total over per-file counts to avoid drift):
    - `test_import_hook.py` – core import/loader behavior and cache semantics.
    - `test_cli.py` – CLI argument handling, `--json`, exit codes, and messaging.
    - `test_cache.py` – cache manager behavior.
    - `test_config.py` – config + settings semantics.
    - `test_discovery.py` – context discovery helpers.
    - `test_llm.py` – LLM client and prompt utilities.
    - `test_logging.py` – logging citizenship (opt-in file logging, levels).
    - `test_safety.py` – security validator rules.
    - `test_types.py` – type registry and serialization.
    - `test_namespaces.py` – static vs dynamic namespace behavior.
    - `test_explore.py` – explore() multi-variant generation.
    - `test_evolve.py` – evolve() generational improvement.

- `examples/` (15 examples, `00`–`14`)
  - `00_quick_start.py` through `06_omg_why.py` – basic usage patterns (`01_json_yaml`, `02_web_scraping`, `03_data_validation`, `04_format_conversion`, `05_api_client`, `06_omg_why`).
  - `07_typed_outputs.py` – demonstrates type registry with Pydantic, dataclasses, TypedDict.
  - `08_dynamic_vs_static.py` – shows difference between static (cached) and dynamic (runtime-aware) namespaces.
  - `09_context_shenanigans.py` – demonstrates context discovery and import-site hints.
  - `10_cosmic_horror_line_by_line.py` – iterative dynamic regeneration showcase.
  - `11_logging.py` – logging configuration and citizenship.
  - `12_explore.py` – demonstrates `wishful.explore()` for multi-variant generation.
  - `13_explore_advanced.py` – LLM-as-judge, code golf, self-improving loops.
  - `14_evolve.py` – generational `wishful.evolve()` (deterministic offline demo with `WISHFUL_FAKE_LLM=1`).

- `docs/ideas/advanced_context_discovery.md`
  - Design/brainstorm document for richer context discovery strategies.

---

## Import Flow Architecture (How the Magic Works)

Understanding the import pipeline is the most important conceptual model for this repo.

1. **Package import & finder installation**
   - `src/wishful/__init__.py` imports `install_finder` from `wishful.core.finder` and calls it at module import time.
   - `install_finder()` inserts a `MagicFinder` instance at the front of `sys.meta_path` (unless already present).

2. **Intercepting `wishful.*` imports**
   - `MagicFinder.find_spec(fullname, path, target)`:
     - Ignores non‑`wishful` modules.
     - If the module corresponds to an **internal** package module (real file under `src/wishful/…`), it returns `None` so normal import mechanisms handle it.
     - For `wishful.static.*` modules, it returns a spec with `MagicLoader(mode="static")`.
     - For `wishful.dynamic.*` modules, it returns a spec with `MagicLoader(mode="dynamic")`.
     - For the root `wishful` namespace (when not resolved by the built‑in package), it can use `MagicPackageLoader`.

3. **Context discovery**
   - Before generating or executing code, `MagicLoader.exec_module` calls `discover(fullname)` from `core.discovery`.
   - `discover()` walks the Python stack to find the import site:
     - Parses the import statement into requested symbol names (e.g. `extract_emails`).
     - Captures lines around the import, plus call-site snippets elsewhere in the file, within a configurable radius (`WISHFUL_CONTEXT_RADIUS` or `wishful.set_context_radius`).
     - **Fetches registered type schemas** from `wishful.types.get_all_type_schemas()`.
     - **Fetches function output type bindings** via `wishful.types.get_output_type_for_function()` for each requested function.
   - Returns an `ImportContext(functions=[...], context=str | None, type_schemas=dict, function_output_types=dict)`.

4. **Cache check and optional LLM generation**
   - Loader queries `cache.read_cached(fullname)`:
     - **Static mode:** If cached source exists, it is used directly (`from_cache=True`). Otherwise `_generate_and_cache` is called and the result is cached.
     - **Dynamic mode:** Always calls `_generate_and_cache` and **never uses cache**, even if it exists. Regenerates on every import to capture runtime context.
     - Generation wraps `generate_module_code(fullname, functions, context, type_schemas, function_output_types)` in a `spinner`.
     - In static mode only, writes the string result to a `.py` file via `cache.write_cached`.

5. **Safety validation and execution**
   - Before executing, `validate_code(source, allow_unsafe=settings.allow_unsafe)` enforces safety.
   - On success, the loader sets `module.__file__` and `module.__package__`, then `exec(compile(...), module.__dict__)`.

6. **Handling missing symbols & dynamic `__getattr__`**
   - If the import specified function names (`from wishful.text import foo, bar`), the loader checks whether those names are present in `module.__dict__`.
   - If names are missing:
     - If source came from cache, it deletes the cached module, regenerates with an expanded function list, and re‑executes the module.
     - If this was already a fresh generation, it raises `GenerationError`.
   - The loader attaches a custom `__getattr__` to the module that:
     - On attribute miss, discovers context again, expands the requested function set (plus existing symbols), regenerates and re‑executes the module, then retries attribute access.

7. **Interactive review (optional)**
   - When `settings.review` is `True`, after generation the source is printed and the user is prompted to approve it before execution. Tests disable this behavior via the fixture.

---

## Configuration & Environment Variables

Configuration is centralized in `src/wishful/config.py` via the `Settings` dataclass and `settings` instance.

### Settings fields

- `model: str` – LLM model identifier (default: `WISHFUL_MODEL` if set, else `DEFAULT_MODEL`, else `"azure/gpt-4.1"`; `WISHFUL_MODEL` takes precedence).
- `cache_dir: Path` – where generated modules are stored (default `.wishful` in CWD).
- `review: bool` – whether to prompt for manual review before executing generated code.
- `debug: bool` – enable verbose logging (sets `log_level` to DEBUG and file logging on unless overridden).
- `allow_unsafe: bool` – bypass safety checks when `True`.
- `spinner: bool` – enable/disable the rich spinner UI.
- `max_tokens: int` – upper bound for LLM response tokens (default 16384).
- `temperature: float` – LLM sampling temperature (default 1.0).
- `system_prompt: str` – system prompt sent to the LLM (default from `WISHFUL_SYSTEM_PROMPT` or a built-in template).
- `log_level: str` – logging level, uppercased (default `"WARNING"`, from `WISHFUL_LOG_LEVEL`).
- `log_to_file: bool` – write logs to `{cache_dir}/_logs/`. **Default `False` (opt-in)** via `WISHFUL_LOG_TO_FILE=1`; a bare `import wishful` creates no files.
- `request_timeout: float` – per-request LLM timeout in seconds (default 300, from `WISHFUL_REQUEST_TIMEOUT`).
- (Context discovery radius is configured separately via `wishful.set_context_radius(n)` or `WISHFUL_CONTEXT_RADIUS`; it is not a `Settings` field.)

Use `wishful.configure(...)` at runtime to change these values programmatically:

```python
import wishful

wishful.configure(model="gpt-4o-mini", review=True, cache_dir=".wishful_dev")
```

Tests heavily rely on `configure()` and `reset_defaults()`; when adding new fields, update:

- `Settings` dataclass (defaults and copy method).
- `configure` function (argument list and assignments).
- `reset_defaults` to propagate new defaults.
- Relevant tests in `tests/test_config.py`.

### Environment variables

Loaded via `python-dotenv` (`load_dotenv()` at module import). Relevant variables include:

- LLM routing (through litellm):
  - `OPENAI_API_KEY`, `DEFAULT_MODEL`, etc., _or_ provider‑specific vars like:
    - `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION`, `DEFAULT_MODEL`.
  - `WISHFUL_MODEL` – sets `settings.model` and **takes precedence over** `DEFAULT_MODEL` (which is only the fallback).
- Wishful behavior:
  - `WISHFUL_CACHE_DIR` – override cache directory path.
  - `WISHFUL_REVIEW` – `"1"` enables review mode.
  - `WISHFUL_DEBUG` – `"1"` enables debug mode (where implemented).
  - `WISHFUL_UNSAFE` – `"1"` disables safety checks (dangerous).
- `WISHFUL_SPINNER` – `"0"` disables the spinner.
- `WISHFUL_MAX_TOKENS` – integer.
- `WISHFUL_TEMPERATURE` – float.
- `WISHFUL_REQUEST_TIMEOUT` – float; per-request LLM timeout in seconds (default 300).
- `WISHFUL_LOG_LEVEL` – logging level (DEBUG, INFO, WARNING, ERROR; default WARNING).
- `WISHFUL_LOG_TO_FILE` – file logging is **off by default**; set to `"1"` to enable.
- `WISHFUL_SYSTEM_PROMPT` – override the system prompt.
- `WISHFUL_CONTEXT_RADIUS` – integer; number of lines before/after import lines and call sites to include in context (default 3).
- `WISHFUL_FAKE_LLM` – `"1"` enables fake, deterministic generation (no network).

When working on the project:

- For offline or deterministic behavior, export `WISHFUL_FAKE_LLM=1` or rely on tests, which avoid real network calls.
- For actual generation experiments, configure litellm via its standard env variables and ensure `WISHFUL_FAKE_LLM` is not set.

---

## Type Registry System

The type registry (`src/wishful/types/`) allows users to register complex types (Pydantic models, dataclasses, TypedDict) so the LLM can generate functions that return properly structured data.

### Using the Type Registry

Basic registration:

```python
import wishful
from dataclasses import dataclass

@wishful.type
@dataclass
class Book:
    """A book with title, author, and year."""
    title: str
    author: str
    year: int
```

Binding types to specific function outputs:

```python
@wishful.type(output_for="parse_user_data")
@dataclass
class UserProfile:
    """User profile with name, email, and age."""
    name: str
    email: str
    age: int
```

Multiple functions sharing a type:

```python
from typing import TypedDict

class ProductInfo(TypedDict):
    """Product information."""
    name: str
    price: float

wishful.type(ProductInfo, output_for=["parse_product", "create_product"])
```

Pydantic models with Field constraints and docstring-driven behavior:

```python
from pydantic import BaseModel, Field

@wishful.type
class ProjectPlan(BaseModel):
    """Project plan written by master yoda from star wars."""
    project_brief: str
    milestones: list[str] = Field(description="list of milestones", min_length=10)
    budget: float = Field(gt=0, description="project budget in USD")
```

The LLM will respect both Field constraints (min_length=10, gt=0) AND the docstring style (generates text in Yoda-speak).

### How It Works

1. **Registration**: The `@wishful.type` decorator registers a type in the global `TypeRegistry`.
2. **Serialization**: When generating code, the registry serializes registered types to Python source code.
3. **Prompt Enhancement**: Type definitions and output bindings are included in the LLM prompt's system message.
4. **Generation**: The LLM generates code that constructs and returns instances of the registered types.

### Implementation Details

- `TypeRegistry._serialize_pydantic()` – extracts Pydantic model fields and types, **includes docstrings**
  - `_build_field_args()` – extracts Pydantic v2 Field constraints from metadata:
    - Parses `field_info.metadata` list for constraint objects: `MinLen`, `MaxLen`, `Gt`, `Ge`, `Lt`, `Le`
    - Extracts `pattern` from `_PydanticGeneralMetadata` objects
    - Supports both Pydantic v1 (direct attributes) and v2 (metadata list) constraint storage
    - Serializes constraints into `Field(description='...', min_length=10, ...)` format
- `TypeRegistry._serialize_dataclass()` – generates dataclass definitions, **includes docstrings**
- `TypeRegistry._serialize_typed_dict()` – formats TypedDict specifications, **includes docstrings**
- Type schemas are passed to `generate_module_code()` as `type_schemas` and `function_output_types`
- **Docstrings influence LLM behavior**: The docstring text (e.g., "Project plan written by master yoda from star wars") is included in the serialized type definition and affects how the LLM generates content (tone, style, domain-specific language)
- See `examples/07_typed_outputs.py` for comprehensive usage examples
- See `tests/test_types.py` for tests covering all scenarios

---

## Explore: Multi-Variant Generation

The `wishful.explore()` function generates multiple implementations of a function and helps you select the best one through testing or benchmarking.

### Basic Usage

```python
import wishful

# Generate 5 variants, return first that passes the test
best = wishful.explore(
    "wishful.static.text.extract_emails",
    variants=5,
    test=lambda fn: fn("test@example.com") == ["test@example.com"]
)

# Use it like any other function
emails = best("Contact us at hello@world.com")

# IMPORTANT: The winning variant is automatically cached!
# Subsequent `from wishful.static.text import extract_emails` uses the proven winner.
```

### Key Feature: Winner Caching

When `explore()` finds a winning variant, it **automatically caches the source code** to `.wishful/` just like a regular wishful import would. This means:

1. **First time**: `wishful.explore("wishful.static.text.extract_emails", ...)` generates multiple variants, tests them, selects the best one, and caches it to `.wishful/text.py`.
2. **Subsequent imports**: `from wishful.static.text import extract_emails` loads the cached winner instantly—no LLM call, no re-exploration.

This makes `explore()` a "smarter" way to populate the cache: instead of generating one implementation and hoping it works, you generate multiple candidates, test them, and cache the **proven** winner.

### API

```python
def explore(
    module_path: str,                # e.g., "wishful.static.text.extract_emails"
    *,
    variants: int = 5,               # Number of variants to generate
    test: Callable[[Callable], bool] | None = None,  # Pass/fail filter
    benchmark: Callable[[Callable], float] | None = None,  # Score function
    optimize: Literal["first_passing", "fastest", "best_score"] = "first_passing",
    timeout_per_variant: float = 30.0,
    return_all: bool = False,        # Return list of all passing variants
    verbose: bool = True,            # Show rich progress display
    save_results: bool = True,       # Save CSV to cache_dir/_explore/
) -> Callable | list[Callable]
```

### Selection Strategies

- **`first_passing`** (default): Return first variant that passes `test`. Fast, good for CI.
- **`fastest`** / **`best_score`**: Run all variants, benchmark each, return highest score.

### Examples

```python
# Benchmark: find fastest implementation
def benchmark_sort(fn):
    import time
    start = time.perf_counter()
    for _ in range(100):
        fn(list(range(1000, 0, -1)))
    return 100 / (time.perf_counter() - start)

fastest = wishful.explore(
    "wishful.static.algorithms.sort_list",
    variants=10,
    benchmark=benchmark_sort,
    optimize="fastest"
)

# Combined: test for correctness, benchmark for speed
best = wishful.explore(
    "wishful.static.data.parse_json",
    variants=5,
    test=lambda fn: fn('{"a":1}') == {"a": 1},
    benchmark=lambda fn: measure_speed(fn),
    optimize="fastest"
)

# Get all passing variants
all_variants = wishful.explore(
    "wishful.static.math.fibonacci",
    variants=5,
    test=lambda fn: fn(10) == 55,
    return_all=True
)
```

### Metadata

Returned functions have `__wishful_metadata__` and `__wishful_source__` attributes:

```python
fn = wishful.explore("wishful.static.text.slugify", variants=3)
print(fn.__wishful_metadata__)
# {'module': 'wishful.static.text', 'function': 'slugify', 'variant_index': 1, ...}
print(fn.__wishful_source__)
# def slugify(text): ...
```

### Error Handling

```python
try:
    fn = wishful.explore("wishful.static.impossible.task", variants=5, test=lambda fn: False)
except wishful.ExplorationError as e:
    print(f"Tried {e.attempts} variants, none passed")
    print(f"Failures: {e.failures}")
```

### Progress Display & Logging

When `verbose=True` (default), explore shows a beautiful rich progress display:

```
╭────────── 🔍 wishful.explore → wishful.static.text.extract_emails ───────────╮
│    Exploring extract_emails ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 3/3 • 0:01:22     │
│  Strategy:  first_passing                                                    │
│  Passed:    1                                                                │
│  Failed:    2                                                                │
│                                   Variants                                   │
│  ┏━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  │
│  ┃   # ┃ Status     ┃    Time ┃      Score ┃ Info                         ┃  │
│  ┡━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩  │
│  │   0 │ error      │   21.5s │          - │ Compile: Failed to compile   │  │
│  │   1 │ timeout    │     ... │          - │ Generation timed out         │  │
│  │   2 │ passed     │   29.2s │          - │ import re from typing import │  │
│  └─────┴────────────┴─────────┴────────────┴──────────────────────────────┘  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

When `save_results=True` (default), results are saved to `cache_dir/_explore/`:
- `{function}_{timestamp}.csv` — Full results for downstream analysis
- `{function}_{timestamp}_summary.txt` — Human-readable summary

### Module Structure

```
src/wishful/explore/
├── __init__.py      # Public API: explore, ExplorationError
├── explorer.py      # Core explore() - async internally, sync API; selection strategies (first_passing, fastest, best_score)
├── variant.py       # VariantMetadata and wrapper
├── exceptions.py    # ExplorationError
└── progress.py      # Rich Live progress display and CSV logging
```

### Implementation Notes

- **Async internally**: `explore()` is sync for ease of use but uses `asyncio` and `litellm.acompletion()` internally for responsive UI updates during generation.
- **Reusable event loop**: Uses a cached event loop to avoid litellm's `LoggingWorker` issues with multiple `asyncio.run()` calls.
- **Winner caching**: After selection, writes the winning source to `.wishful/` via `cache.manager.write_cached()`.
- **Conditional Score column**: The Rich display hides the Score column when no benchmark is provided.

- See `examples/12_explore.py` for comprehensive usage examples
- See `tests/test_explore.py` for tests covering all scenarios

---

## Cache & CLI Behavior

### Cache layout

- The root cache directory is `settings.cache_dir` (default `.wishful` under the current working directory).
- `cache.manager.module_path(fullname)`:
  - Strips leading `wishful.` from the module name.
  - **Also strips `static` and `dynamic` namespace prefixes** so both `wishful.static.text` and `wishful.dynamic.text` map to the same cache file.
  - Converts dots to directories and appends `.py`.
  - Example: `"wishful.static.text"` → `.wishful/text.py`, `"wishful.dynamic.text"` → `.wishful/text.py`.
- Utilities in `cache.manager`:
  - `read_cached(fullname)` → `str | None`
  - `write_cached(fullname, source)` → `Path`
  - `delete_cached(fullname)` / `clear_cache()` / `inspect_cache()` / `has_cached(fullname)`

The top‑level public API in `wishful.__init__` re‑exports high‑level cache helpers:

- `wishful.clear_cache()`
- `wishful.inspect_cache()`
- `wishful.regenerate(module_name)` – defaults to static namespace if no prefix given

### CLI (`wishful` / `python -m wishful`)

Via `src/wishful/__main__.py`. The `wishful` console script (`[project.scripts]`) and `python -m wishful` are equivalent entry points; both call `main()`.

- `wishful` (no args) – prints help and usage.
- `wishful inspect` – shows current cached modules under `settings.cache_dir`.
- `wishful clear` – clears the cache directory.
- `wishful regen wishful.static.text` – deletes cache for the given module so it is regenerated on next import (a bare name like `text` maps into the static namespace).
- `wishful --version` – prints `wishful.__version__`.
- Every subcommand accepts `--json` for machine-readable output.
- Exit codes: `0` success, `1` runtime error (e.g. invalid module name), `2` usage error (argparse).

From this repo, always invoke via uv (the console script also works once synced):

```bash
uv run python -m wishful inspect
uv run python -m wishful regen wishful.static.text
```

If you modify CLI behavior, update tests in `tests/test_cli.py` accordingly.

---

## LLM Integration Details

The only place that calls the LLM is `src/wishful/llm/client.py`.

- `generate_module_code(module: str, functions: Sequence[str], context: str | None, type_schemas: dict[str, str] | None, function_output_types: dict[str, str] | None) -> str`
  - If `WISHFUL_FAKE_LLM=1`, returns stub implementations from `_fake_response`:
    - For each requested function, generates a placeholder that returns its args/kwargs.
  - Otherwise:
    - Builds messages via `build_messages`.
    - Calls `litellm.completion` with:
      - `model=settings.model`
      - `temperature=settings.temperature`
      - `max_tokens=settings.max_tokens`
    - Extracts the returned content, strips markdown code fences, and returns the raw Python source string.
  - Raises `GenerationError` on failure or empty responses.

- `prompts.build_messages(module, functions, context, type_schemas, function_output_types)`:
  - `system` message:
    - Instructs the model to emit **only executable Python code**, no markdown fences.
    - Encourages simple, readable code.
    - Explicitly states "You may use any Python libraries available in the environment" (Pydantic, requests, etc.).
    - Explicitly discourages network, filesystem writes, subprocess, shell execution.
    - **Includes registered type schemas** when available, formatted as Python class definitions.
    - **Specifies output types** for specific functions when registered via `@wishful.type(output_for=...)`.
  - `user` message:
    - Contains module name and list of functions to implement.
    - Includes discovered context (comments/nearby code) as a block when available.

When extending or adjusting LLM behavior:

- Keep the **single entry point** concept — avoid sprinkling raw `litellm` calls elsewhere.
- Update or add tests in `tests/test_llm.py`.
- Consider how changes interact with `WISHFUL_FAKE_LLM` and offline usage.

---

## Runtime Invariants & Reload Gotchas

- **Settings singleton lives on `builtins`** (`builtins._wishful_settings`). All imports must share this object so log/config state survives test-time module reloads. Don’t replace it; mutate via `wishful.configure()` / `reset_defaults()`.
- **Finder is idempotent by class+module name.** `install_finder()` skips adding another `MagicFinder` if one from `wishful.core.finder` is already on `sys.meta_path`; avoid manually inserting your own finder.
- **Loader honors monkeypatches at call time.** `MagicLoader` resolves `generate_module_code` for each generation, so patching `wishful.core.loader.generate_module_code` (or in tests) works even after module reloads.
- **When clearing `sys.modules`,** tests typically remove only `wishful.static.*` / `wishful.dynamic.*` (and sometimes `wishful`); keep internal modules unless you have a specific reason, to avoid losing shared singletons.

## Safety Model

Safety is enforced in `src/wishful/safety/validator.py` via `validate_code(source, allow_unsafe=False)`.

Key rules (when `allow_unsafe` is `False`):

- Forbidden imports:
  - Top‑level `os`, `subprocess`, `sys` (including `from os import path` etc.).
- Forbidden calls:
  - `eval()` and `exec()` anywhere.
  - `open()` in write/append/update modes (`"w"`, `"a"`, `"+"`) whether positional or keyword `mode` arg.
  - `os.*` and `subprocess.*` when used as call targets (e.g. `os.system(...)`, `subprocess.call(...)`), even through aliases.
- Extra guard:
  - If the AST contains any names from the forbidden call set, it raises a `SecurityError`.

In tests, the fixture sets `allow_unsafe=True` to avoid blocking test code that uses these constructs intentionally.

When modifying safety:

- Treat the current rules as a **baseline minimum**.
- If relaxing any rule, update/add tests in `tests/test_safety.py` and, if necessary, add new tests to cover edge cases.
- If tightening rules, ensure they do not break sensible generated code for common use cases.

---

## Testing: How to Run & What to Expect

All tests use `pytest` and expect to be run via `uv`.

Common commands:

```bash
# Full suite
uv run pytest -q

# Verbose, all tests
uv run pytest tests/ -v

# Single file
uv run pytest tests/test_import_hook.py -v
```

Test infra details:

- `conftest.reset_wishful` is `autouse=True`, so every test:
  - Points `cache_dir` at a per‑test `tmp_path / ".wishful"`.
  - Disables spinner and interactive review.
  - Sets `allow_unsafe=True`.
  - Clears cache and resets settings between tests.
  - Purges `wishful` and `wishful.*` from `sys.modules`.
- Many tests monkeypatch `loader.generate_module_code` or other internals to avoid network and simulate specific behaviors.

When adding tests:

- Prefer to rely on the existing fixture rather than manually tweaking global settings.
- For new modules, place tests under `tests/` and follow the naming pattern `test_*.py`.
- When behavior is tied to CLI or caching, assert both side effects (e.g. files created/removed) and user‑visible output.

---

## Common Agent Tasks & Recipes

### 1. Add a new configuration option

Steps:

1. Add a field to `Settings` with a sensible default.
2. Extend `configure` with an optional parameter and apply it to `settings`.
3. Update `reset_defaults` to copy the new field from a fresh `Settings()` instance.
4. Add tests to `tests/test_config.py`.
5. If the setting affects behavior elsewhere (e.g. in discovery or loader), propagate it and add tests there.

Remember: run tests via `uv run pytest`.

### 2. Change context discovery behavior

Files:

- `src/wishful/core/discovery.py`
- Reference: `docs/ideas/advanced_context_discovery.md`

Considerations:

- Keep the `ImportContext` abstraction (`functions`, `context`) intact unless you also update all consumers.
- Avoid heavy introspection or expensive file scanning on every import; keep discovery lightweight.
- If you add new context fields, extend prompt building appropriately and update tests in `tests/test_discovery.py` and possibly `tests/test_llm.py`.

### 3. Extend CLI commands

File: `src/wishful/__main__.py`

Guidelines:

- Follow the existing pattern: parse `sys.argv`, handle subcommands, print user‑friendly messages, and exit with appropriate codes.
- Update or add tests in `tests/test_cli.py`.
- Ensure new commands still respect `settings.cache_dir` and other global config.

### 4. Adjust cache behavior

File: `src/wishful/cache/manager.py`

Guidelines:

- Keep the basic mapping from module name → `.py` in `cache_dir`.
- When changing the directory layout, update:
  - `MagicPackageLoader` (if needed).
  - CLI messages that mention cache paths.
  - Tests in `tests/test_cache.py`, `tests/test_cli.py`, and import‑hook tests that inspect cache.

---

## Coding Style & Conventions

- **Type hints:** the codebase is typed, and `py.typed` is present. Maintain type annotations for new functions and classes.
- **Imports:** prefer standard library where possible. Non‑standard dependencies should be minimal and declared via `uv add`.
- **Docstrings:** public functions and classes should have concise docstrings, especially those forming the user‑facing API.
- **Side effects at import time:**
  - `wishful.__init__` installing the finder is intentional.
  - Avoid adding additional heavy side effects at import; keep imports cheap.
- **Error handling:**
  - Use specific custom exceptions (`GenerationError`, `SecurityError`) where appropriate.
  - Let `ImportError`‑style errors surface when import semantics are violated.

If in doubt, follow patterns used in existing modules (`config.py`, `loader.py`, etc.).

---

## Working With External APIs (litellm)

- All external LLM access is mediated by `litellm` inside `wishful.llm.client`.
- When experimenting locally:
  - Configure your provider (OpenAI, Azure, others) via environment variables recognized by `litellm`.
  - Set `DEFAULT_MODEL` or `WISHFUL_MODEL` to point at the provider/model you want.
- For CI or non‑network environments:
  - Use `WISHFUL_FAKE_LLM=1` or rely on tests that avoid real network calls.

Do not add provider‑specific logic directly into wishful modules; keep things generic and let `litellm` handle providers.

---

## Final Notes for Future Agents

- **Use `uv` for everything** inside this repo:
  - `uv sync`, `uv run`, `uv add`, `uv lock`.
  - Avoid raw `pip`, `virtualenv`, or `python` commands for project tasks.
- **Versioning:** Before committing, bump the patch version in `pyproject.toml` (keep major/minor unless intentionally releasing). This keeps published artifacts and commits aligned.
- Before larger refactors:
  - Read this file plus `README.md` and, if relevant, `docs/ideas/advanced_context_discovery.md`.
  - Skim the matching test file(s) to understand expected behavior.
- After changes:
  - Run the focused tests for the area you touched via `uv run pytest …`.
  - Optionally run the full suite before opening a PR or handing off work.

With these guidelines, you should be able to work effectively on `wishful` without extensive exploratory digging. Happy wishing! ✨
