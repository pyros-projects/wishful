# Changelog

All notable changes to wishful will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2024-11-24

### Added

#### 🎨 Type Registry System
- **Type registration decorator** (`@wishful.type`) for Pydantic models, dataclasses, and TypedDict
- **Pydantic Field constraint support**: LLM now respects `min_length`, `max_length`, `gt`, `ge`, `lt`, `le`, and `pattern` constraints
- **Docstring-driven LLM behavior**: Class docstrings influence generated code tone and style (e.g., "written by master yoda" generates Yoda-speak)
- **Type binding to functions**: `@wishful.type(output_for="function_name")` tells LLM which functions should return which types
- **Multi-function type sharing**: `wishful.type(TypeClass, output_for=["func1", "func2"])` for shared types

#### 🔄 Static vs Dynamic Namespaces
- **`wishful.static.*` namespace**: Cached generation (default behavior, fast subsequent imports)
- **`wishful.dynamic.*` namespace**: Runtime-aware regeneration on every import (for creative/contextual content)
- Both namespaces share the same cache file for consistency

#### 🧠 Enhanced Context Discovery
- **Type schema integration**: Registered types are automatically included in LLM prompts
- **Function output type hints**: LLM receives information about expected return types
- Type definitions are serialized with full docstrings and Field constraints

#### 📦 Pydantic v2 Support
- **Metadata-based constraint extraction**: Properly parses Pydantic v2's constraint storage (`MinLen`, `MaxLen`, `Gt`, etc.)
- **`_PydanticGeneralMetadata` handling**: Extracts `pattern` and other general constraints
- **Backward compatibility**: Still supports Pydantic v1 direct attribute access

### Changed

#### System Prompt Updates
- **External library support**: Changed from "only use Python standard library" to "you may use any Python libraries available in the environment"
- Pydantic, requests, and other common libraries now explicitly allowed in generated code

#### Examples
- Added `07_typed_outputs.py`: Comprehensive type registry demonstration
- Added `08_dynamic_vs_static.py`: Static vs dynamic namespace comparison
- Added `09_context_shenanigans.py`: Context discovery behavior showcase
- All examples updated to use `wishful.static.*` namespace convention

#### Documentation
- **AGENTS.md**: Complete sync with current codebase state
  - Added Pydantic Field constraint documentation
  - Added docstring influence documentation
  - Added type registry implementation details
  - Updated TDD process documentation
- **README.md**: Added type registry section, static/dynamic namespace explanation, and updated FAQ

### Internal Improvements

#### Type Registry (`src/wishful/types/`)
- `_build_field_args()`: New method to extract Field() arguments from Pydantic field_info
- `_serialize_pydantic()`: Enhanced to include Field constraints in serialized schemas
- Docstring serialization for all type systems (Pydantic, dataclass, TypedDict)

#### Discovery System (`src/wishful/core/discovery.py`)
- `ImportContext`: Extended with `type_schemas` and `function_output_types` fields
- `discover()`: Now fetches registered type schemas and output type bindings
- Integration with `wishful.types.get_all_type_schemas()` and `get_output_type_for_function()`

#### LLM Prompts (`src/wishful/llm/prompts.py`)
- Enhanced `build_messages()` to include type definitions in prompts
- System prompt updated to allow external libraries
- Type schemas formatted as executable Python code for LLM

### Tests
- **83 total tests** with **80% code coverage**
- Added 4 new tests in `test_discovery.py` for type registry integration
- Added 30 tests in `test_types.py` for type serialization (all scenarios)
- Added 6 tests in `test_namespaces.py` for static vs dynamic behavior

### Dependencies
- Added `pydantic>=2.12.4` as runtime dependency

---

## [0.1.6] - 2024-11-XX

### Initial Release
- Basic import hook system with LLM code generation
- Cache management (static `.wishful/` directory)
- Context discovery from import sites
- Safety validation (AST-based checks)
- CLI interface (`wishful inspect`, `clear`, `regen`)
- Configuration system with environment variables
- litellm integration for multi-provider LLM support
- Fake LLM mode for deterministic testing (`WISHFUL_FAKE_LLM=1`)

---

[0.2.0]: https://github.com/pyros-projects/wishful/compare/v0.1.6...v0.2.0
[0.1.6]: https://github.com/pyros-projects/wishful/releases/tag/v0.1.6
