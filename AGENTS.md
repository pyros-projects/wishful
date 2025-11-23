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

- Runtime deps: `litellm`, `rich`, `python-dotenv`
- Dev deps: `pytest` (and anything else added via `uv add --dev`)

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

---

## High‑Level Overview

**wishful** lets users write imports like:

```python
from wishful.text import extract_emails
```

and, on first import, an LLM generates the implementation on the fly. The generated module is cached as plain Python in a configurable directory (default `.wishful/`). Subsequent imports use the cache without calling the LLM again.

Key properties:

- Uses a custom **import hook** (meta‑path finder + loader).
- **Context‑aware**: forwards nearby comments/code lines to the LLM as hints.
- **Safety‑checked**: generated code is parsed and checked for obviously dangerous constructs.
- **Cache‑backed**: generated modules live as `.py` files and can be edited or committed.

---

## Repository Layout

From the root:

- `pyproject.toml`  
  - Project metadata: name, version, description.
  - `requires-python = ">=3.12"`.
  - Runtime deps: `litellm`, `rich`, `python-dotenv`.
  - Dev deps under `[dependency-groups].dev`: `pytest`.
  - Build system uses `uv_build` as backend.

- `uv.lock`  
  - uv’s lockfile. Treat as generated; do not hand‑edit.

- `src/wishful/` – main package
  - `__init__.py`  
    - Public API: `configure`, `clear_cache`, `inspect_cache`, `regenerate`, `SecurityError`, `GenerationError`.
    - Installs the import finder on import (`install_finder()`), so `import wishful` activates the magic.
  - `__main__.py`  
    - CLI entry point (`python -m wishful`).
    - Provides `inspect`, `clear`, `regen` subcommands, all wired to cache and config.
  - `config.py`  
    - Defines the `Settings` dataclass and the global `settings` instance.
    - Reads environment variables (e.g. `DEFAULT_MODEL`, `WISHFUL_MODEL`, `WISHFUL_CACHE_DIR`, `WISHFUL_*` flags).
    - Provides `configure(**kwargs)` and `reset_defaults()` utilities.
  - `core/` – import mechanics
    - `__init__.py` – re‑exports `MagicFinder`, `MagicLoader`, `install`.
    - `finder.py` – `MagicFinder` (meta‑path finder) that intercepts `wishful.*` imports and delegates to `MagicLoader` unless the module is part of the built‑in package.
    - `loader.py` – `MagicLoader` and `MagicPackageLoader`:
      - Handles cache lookup, LLM generation, dynamic regeneration when requested symbols are missing, and dynamic `__getattr__` for on‑demand symbols.
  - `cache/` – cache management
    - `manager.py` – cache path computation, read/write, clear, list.
  - `llm/`
    - `client.py` – wraps `litellm` calls and exposes `generate_module_code`, `GenerationError`.
    - `_FAKE_MODE` via `WISHFUL_FAKE_LLM=1` returns deterministic stubs (no network).
    - `prompts.py` – prompt construction (`build_messages`) and `strip_code_fences`.
  - `safety/`
    - `validator.py` – `validate_code(source, allow_unsafe)` plus `SecurityError`.
    - AST‑based checks for forbidden imports (`os`, `subprocess`, `sys`), forbidden calls (`eval`, `exec`, unsafe `open`, `os.system`, `subprocess.*`, etc.).
  - `ui.py`
    - `spinner(message)` context manager using `rich` to show an optional spinner (controlled by `settings.spinner`).

- `tests/`
  - `conftest.py` – `reset_wishful` fixture:
    - Forces per‑test cache dir under `tmp_path`.
    - Disables spinner and interactive review.
    - Sets `allow_unsafe=True` for tests, wipes modules and cache between tests.
  - Individual test modules:
    - `test_import_hook.py` – core import/loader behavior and cache semantics.
    - `test_cli.py` – CLI argument handling and messaging.
    - `test_cache.py` – cache manager behavior.
    - `test_config.py` – config + settings semantics.
    - `test_discovery.py` – context discovery helpers.
    - `test_llm.py` – LLM client and prompt utilities.
    - `test_safety.py` – security validator rules.

- `examples/`
  - `00_quick_start.py` and others – small scripts demonstrating common usage patterns.

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
     - For external dynamic modules (e.g. `wishful.text`, `wishful.dates`…), it returns a spec with `MagicLoader` and `is_package=False`.
     - For the root `wishful` namespace (when not resolved by the built‑in package), it can use `MagicPackageLoader`.

3. **Context discovery**
   - Before generating or executing code, `MagicLoader.exec_module` calls `discover(fullname)` from `core.discovery`.
   - `discover()` walks the Python stack to find the import site:
     - Parses the import statement into requested symbol names (e.g. `extract_emails`).
     - Captures lines around the import, plus call-site snippets elsewhere in the file, within a configurable radius (`WISHFUL_CONTEXT_RADIUS` or `wishful.set_context_radius`).
   - Returns an `ImportContext(functions=[...], context=str | None)`.

4. **Cache check and optional LLM generation**
   - Loader queries `cache.read_cached(fullname)`:
     - If cached source exists, it is used directly (`from_cache=True`).
     - Otherwise `_generate_and_cache` is called:
       - Wraps `generate_module_code(fullname, functions, context)` in a `spinner`.
       - Writes the string result to a `.py` file via `cache.write_cached`.

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

- `model: str` – LLM model identifier (default from `DEFAULT_MODEL` / `WISHFUL_MODEL` or `"azure/gpt-4.1"`).
- `cache_dir: Path` – where generated modules are stored (default `.wishful` in CWD).
- `review: bool` – whether to prompt for manual review before executing generated code.
- `debug: bool` – enable verbose logging (currently a simple flag used where needed).
- `allow_unsafe: bool` – bypass safety checks when `True`.
- `spinner: bool` – enable/disable the rich spinner UI.
- `max_tokens: int` – upper bound for LLM response tokens.
- `temperature: float` – LLM sampling temperature.
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
  - `WISHFUL_MODEL` – alternative way to set `settings.model`.
- Wishful behavior:
  - `WISHFUL_CACHE_DIR` – override cache directory path.
  - `WISHFUL_REVIEW` – `"1"` enables review mode.
  - `WISHFUL_DEBUG` – `"1"` enables debug mode (where implemented).
  - `WISHFUL_UNSAFE` – `"1"` disables safety checks (dangerous).
- `WISHFUL_SPINNER` – `"0"` disables the spinner.
- `WISHFUL_MAX_TOKENS` – integer.
- `WISHFUL_TEMPERATURE` – float.
- `WISHFUL_CONTEXT_RADIUS` – integer; number of lines before/after import lines and call sites to include in context (default 3).
- `WISHFUL_FAKE_LLM` – `"1"` enables fake, deterministic generation (no network).

When working on the project:

- For offline or deterministic behavior, export `WISHFUL_FAKE_LLM=1` or rely on tests, which avoid real network calls.
- For actual generation experiments, configure litellm via its standard env variables and ensure `WISHFUL_FAKE_LLM` is not set.

---

## Cache & CLI Behavior

### Cache layout

- The root cache directory is `settings.cache_dir` (default `.wishful` under the current working directory).
- `cache.manager.module_path(fullname)`:
  - Strips leading `wishful.` from the module name.
  - Converts dots to directories and appends `.py`.
  - Example: `"wishful.text"` → `.wishful/text.py`.
- Utilities in `cache.manager`:
  - `read_cached(fullname)` → `str | None`
  - `write_cached(fullname, source)` → `Path`
  - `delete_cached(fullname)` / `clear_cache()` / `inspect_cache()` / `has_cached(fullname)`

The top‑level public API in `wishful.__init__` re‑exports high‑level cache helpers:

- `wishful.clear_cache()`
- `wishful.inspect_cache()`
- `wishful.regenerate(module_name)`

### CLI (`python -m wishful`)

Via `src/wishful/__main__.py`:

- `python -m wishful` – prints help and usage.
- `python -m wishful inspect` – shows current cached modules under `settings.cache_dir`.
- `python -m wishful clear` – clears the cache directory.
- `python -m wishful regen wishful.text` – deletes cache for the given module so it is regenerated on next import.

From this repo, always invoke via uv:

```bash
uv run python -m wishful inspect
uv run python -m wishful regen wishful.text
```

If you modify CLI behavior, update tests in `tests/test_cli.py` accordingly.

---

## LLM Integration Details

The only place that calls the LLM is `src/wishful/llm/client.py`.

- `generate_module_code(module: str, functions: Sequence[str], context: str | None) -> str`
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

- `prompts.build_messages(module, functions, context)`:
  - `system` message:
    - Instructs the model to emit **only executable Python code**, no markdown fences.
    - Encourages simple, readable, standard‑library‑only code.
    - Explicitly discourages network, filesystem writes, subprocess, shell execution.
  - `user` message:
    - Contains module name and list of functions to implement.
    - Includes discovered context (comments/nearby code) as a block when available.

When extending or adjusting LLM behavior:

- Keep the **single entry point** concept — avoid sprinkling raw `litellm` calls elsewhere.
- Update or add tests in `tests/test_llm.py`.
- Consider how changes interact with `WISHFUL_FAKE_LLM` and offline usage.

---

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
