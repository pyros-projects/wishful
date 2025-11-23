# Wishful - AI Coding Agent Instructions

## Project Overview

**wishful** is a Python import hook that uses LLMs to generate code on-demand. When you `from wishful.foo import bar`, if `bar` doesn't exist, an LLM generates it based on context clues and caches the result as regular Python in `.wishful/`.

**Core Flow**: Import → MetaPathFinder intercepts → Check cache → (if miss) LLM generates → AST validation → Cache → Execute

## Architecture

### Import Hook Pipeline (`src/wishful/core/`)
- **`finder.py`**: `MagicFinder` on `sys.meta_path` intercepts `wishful.*` imports
- **`loader.py`**: `MagicLoader.exec_module()` orchestrates: cache check → LLM call → validation → dynamic `__getattr__` for lazy symbol generation
- **`discovery.py`**: Stack inspection to extract function names from import statements and grab surrounding comment context (the "desired:" hints)

### LLM Integration (`src/wishful/llm/`)
- Uses `litellm` for multi-provider support (OpenAI, Azure, local models)
- **`prompts.py`**: Builds system prompt emphasizing stdlib-only, no network/filesystem writes
- **Fake mode**: `WISHFUL_FAKE_LLM=1` generates deterministic stubs for testing (see `_fake_response()` in `client.py`)

### Safety (`src/wishful/safety/validator.py`)
- AST-based validation blocks: `os`, `subprocess`, `sys` imports; `eval`/`exec` calls; `open()` in write modes
- Override with `allow_unsafe=True` or `WISHFUL_UNSAFE=1` (document risks!)

### Cache (`src/wishful/cache/manager.py`)
- Default: `.wishful/` directory (configurable via `WISHFUL_CACHE_DIR`)
- Cache files are plain Python—edit directly to tweak generated code
- Cache invalidation: `wishful.regenerate("module.name")` or `wishful.clear_cache()`

## Key Conventions

### Context Discovery Pattern
The system reads comments AFTER import statements as hints:
```python
# desired: parse nginx combined logs into list of dicts
from wishful.logs import parse_nginx_logs
```
`discovery.py` extracts `parse_nginx_logs` as function name + the comment as context. Use this pattern in examples.

### Dynamic Symbol Resolution
If you import additional symbols from an already-loaded module, `__getattr__` in `loader.py` regenerates the module WITH ALL previously declared symbols + the new one. This preserves existing functions while adding new ones.

### Test Patterns
- **Fake LLM**: Monkeypatch `loader.generate_module_code` to inject deterministic responses (see `tests/test_import_hook.py`)
- **Module reset**: Call `_reset_modules()` helper to clear `sys.modules` and force reimport
- **Cache isolation**: Use `manager.clear_cache()` + custom `cache_dir` in tests

## Development Workflows

### Running Examples
```bash
# With real LLM (requires API keys in .env)
uv run python examples/00_quick_start.py

# Deterministic mode for CI/testing
WISHFUL_FAKE_LLM=1 uv run python examples/00_quick_start.py
```

### Testing
```bash
uv run pytest tests/ -v                    # Full suite
uv run pytest tests/test_import_hook.py -v # Specific file
uv run pytest --cov=wishful tests/         # With coverage
```

### CLI Commands
```bash
python -m wishful inspect          # List cached modules
python -m wishful clear            # Nuke cache
python -m wishful regen wishful.text  # Force regeneration
```

### Adding Safety Rules
Edit `_FORBIDDEN_IMPORTS`, `_FORBIDDEN_CALLS`, `_FORBIDDEN_FUNCTIONS` in `safety/validator.py`. The validator walks the AST to detect banned patterns—see `validate_code()` for examples.

## Common Gotchas

1. **Internal modules bypass hook**: `finder.py` checks if a module exists in `src/wishful/` before triggering generation. Don't name generated modules same as internal packages (`cache`, `core`, `llm`, `safety`, `ui`).

2. **Symbol regeneration triggers**: If cached code lacks an imported symbol, `loader.py` regenerates ONCE. If still missing, raises `GenerationError`.

3. **Context radius**: `discovery.py` grabs ±3 lines around the import. Keep hints close to the import statement.

4. **litellm model names**: Use format like `azure/gpt-4.1` or `gpt-4o-mini`. Set via `DEFAULT_MODEL` or `WISHFUL_MODEL` env vars.

5. **Cache invalidation**: Manual edits to `.wishful/*.py` persist until `regenerate()` or `clear_cache()` is called.

## Configuration Reference

Environment variables (loaded from `.env` via `python-dotenv`):
- `DEFAULT_MODEL` / `WISHFUL_MODEL`: LLM model identifier
- `WISHFUL_CACHE_DIR`: Cache location (default: `.wishful`)
- `WISHFUL_FAKE_LLM=1`: Use stub generator instead of real LLM
- `WISHFUL_UNSAFE=1`: Disable AST safety checks (use cautiously)
- `WISHFUL_REVIEW=1`: Prompt user to approve code before execution
- `WISHFUL_DEBUG=1`: Verbose logging
- `WISHFUL_SPINNER=0`: Disable generation spinner
- `WISHFUL_MAX_TOKENS`: LLM max tokens (default: 4096)
- `WISHFUL_TEMPERATURE`: LLM creativity (default: 1)

Runtime configuration via `wishful.configure(model=..., cache_dir=..., review=True, ...)`.

## Extending the System

### Adding LLM Providers
`litellm` handles provider routing. Just set credentials per provider docs (e.g., `ANTHROPIC_API_KEY` for Claude).

### Custom Safety Rules
Subclass or extend `validator.py` checks. Consider adding semantic analysis for more sophisticated blocking.

### Context Enrichment
Modify `discovery.py` to capture more context (e.g., type annotations, nearby class definitions). Current implementation uses `linecache` + stack inspection.

## Example Scenarios

**User wants to add a feature requiring new forbidden imports** (e.g., `requests`):
1. Update `safety/validator.py` to allow the import (or add to safe list)
2. Update `llm/prompts.py` system message to permit network calls
3. Document the security implications in README

**Generated code has syntax errors**:
- Check `llm/prompts.py` system prompt—emphasize "valid Python syntax"
- Lower temperature (more deterministic) or try different model
- Inspect `.wishful/<module>.py` to see what was generated
- Use `WISHFUL_REVIEW=1` to preview before execution

**Need to test a new discovery pattern**:
- Write test in `tests/test_discovery.py` with crafted source snippets
- Use `linecache.cache` dict to inject fake file content for stack inspection
