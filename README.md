

<p align="center">
  <img alt="Wishful Banner" src="docs-site/src/content/imgs/wishful_logo (5).jpg" width="800">
</p>

<p align="center">
  <a href="https://badge.fury.io/py/wishful"><img src="https://badge.fury.io/py/wishful.svg" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://github.com/pyros-projects/wishful"><img src="https://img.shields.io/badge/tests-83%20passed-brightgreen.svg" alt="Tests"></a>
  <a href="https://github.com/pyros-projects/wishful"><img src="https://img.shields.io/badge/coverage-80%25-green.svg" alt="Coverage"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/badge/code%20style-ruff-000000.svg" alt="Code style: ruff"></a>
</p>

<p align="center">
  <em>"Import your wildest dreams"</em>
</p>


Stop writing boilerplate. Start wishing for it instead.

**wishful** turns your wildest import dreams into reality. Just write the import you _wish_ existed, and an LLM conjures up the code on the spot. The first run? Pure magic. Every run after? Blazing fast, because it's cached like real Python.

Think of it as **wishful thinking, but for imports**. The kind that actually works.

## ✨ Quick Wish

**1. Install the dream**

```bash
pip install wishful
```

**2. Set your API key** (any provider supported by [litellm](https://docs.litellm.ai/))

```bash
export OPENAI_API_KEY=your_key_here
# or AZURE_API_KEY, ANTHROPIC_API_KEY, etc.
```

**3. Import your wildest fantasies**

```python
from wishful.static.text import extract_emails
from wishful.static.dates import to_yyyy_mm_dd

raw = "Contact us at team@example.com or sales@demo.dev"
print(extract_emails(raw))  # ['team@example.com', 'sales@demo.dev']
print(to_yyyy_mm_dd("31.12.2025"))  # '2025-12-31'
```

**What just happened?**

- **First import**: wishful waves its wand 🪄, asks the LLM to write `extract_emails` and `to_yyyy_mm_dd`, validates the code for safety, and caches it to `.wishful/text.py` and `.wishful/dates.py`.
- **Every subsequent run**: instant. Just regular Python imports. No latency, no drama, no API calls.

It's like having a junior dev who never sleeps and always delivers exactly what you asked for (well, _almost_ always).

> 💡 **Pro tip**: Use `wishful.static.*` for cached imports (recommended) or `wishful.dynamic.*` for runtime-aware regeneration. See [Static vs Dynamic](#-static-vs-dynamic-when-to-use-which) below.

---

## 🎯 Wishful Guidance: Help the AI Read Your Mind

Want better results? Drop hints. Literal comments. wishful reads the code _around_ your import and forwards that context to the LLM. It's like pair programming, but your partner is a disembodied intelligence with questionable opinions about semicolons.

```python
# desired: parse standard nginx combined logs into list of dicts
from wishful.static.logs import parse_nginx_logs

records = parse_nginx_logs(Path("/var/log/nginx/access.log").read_text())
```

---

## 🎨 Type Registry: Teach the AI Your Data Structures

Want the LLM to generate functions that return **properly structured data**? Register your types with `@wishful.type`:

### Pydantic Models with Constraints

```python
from pydantic import BaseModel, Field
import wishful

@wishful.type
class ProjectPlan(BaseModel):
    """Project plan written by master yoda from star wars."""
    project_brief: str
    milestones: list[str] = Field(description="list of milestones", min_length=10)
    budget: float = Field(gt=0, description="project budget in USD")

# Now the LLM knows about ProjectPlan and will respect Field constraints!
from wishful.static.pm import project_plan_generator

plan = project_plan_generator(idea="sudoku web app")
print(plan.milestones)  
# ['Decide, you must, key features.', 'Wireframe, you will, the interface.', ...]
# ^ 10+ milestones in Yoda-speak because of the docstring! 🎭
```

**What's happening here?**
- The `@wishful.type` decorator registers your Pydantic model
- The **docstring** influences the LLM's tone/style (Yoda-speak!)
- **Field constraints** (`min_length=10`, `gt=0`) are actually enforced
- Generated code uses your exact type definition

### Dataclasses and TypedDict Too

```python
from dataclasses import dataclass
from typing import TypedDict

@wishful.type(output_for="parse_user_data")
@dataclass
class UserProfile:
    """User profile with name, email, and age."""
    name: str
    email: str
    age: int

class ProductInfo(TypedDict):
    """Product information."""
    name: str
    price: float
    in_stock: bool

# Tell the LLM multiple functions use this type
wishful.type(ProductInfo, output_for=["parse_product", "create_product"])
```

The LLM will generate functions that return instances of your registered types. It's like having an API contract, but the implementation writes itself. ✨

---

## 🔄 Static vs Dynamic: When to Use Which

wishful supports two import modes:

### `wishful.static.*` — Cached & Consistent (Default)

```python
from wishful.static.text import extract_emails
```

- ✅ **Cached**: Generated once, reused forever
- ✅ **Fast**: No LLM calls after first import
- ✅ **Editable**: Tweak `.wishful/text.py` directly
- 👉 **Use for**: utilities, parsers, validators, anything stable

### `wishful.dynamic.*` — Runtime-Aware & Fresh

```python
# when importing as dynamic module all bets are off
import wishful.dynamic.content as magical_content

my_intro = magical_content.create_a_cosmic_horrorstory_intro()
```

- 🔄 **Regenerates**: Fresh LLM call on every import
- 🎯 **Context-aware**: Captures runtime context each time
- 🎨 **Creative**: Different results on each run
- 👉 **Use for**: creative content, experiments, testing variations

**Note**: Dynamic imports always regenerate and never use the cache, even if a cached version exists. This ensures fresh, context-aware results every time.

---

## 🗄️ Cache Ops: Because Sometimes Wishes Need Revising

```python
import wishful

# See what you've wished for
wishful.inspect_cache()   # ['.wishful/text.py', '.wishful/dates.py']

# Regenerate a module
wishful.regenerate("wishful.static.text")

# Force fresh import (useful for dynamic imports in loops)
story = wishful.reimport('wishful.dynamic.story')

# Nuclear option: forget everything
wishful.clear_cache()
```

**CLI**: `wishful inspect`, `wishful clear`, `wishful regen <module>`

The cache is just regular Python files in `.wishful/`. Want to tweak the generated code? Edit it directly. It's your wish, after all.

---

## ⚙️ Configuration: Fine-Tune Your Wishes

```python
import wishful

wishful.configure(
    model="gpt-4o-mini",        # Switch models like changing channels
    cache_dir="/tmp/.wishful",  # Hide your wishes somewhere else
    spinner=False,              # Silence the "generating..." spinner
    review=True,                # Review code before it runs
    context_radius=6,           # Lines of context (default: 3)
    allow_unsafe=False,         # Keep safety rails ON (recommended)
)
```

**Environment variables**: `WISHFUL_MODEL`, `WISHFUL_CACHE_DIR`, `WISHFUL_REVIEW`, `WISHFUL_DEBUG`, `WISHFUL_UNSAFE`, `WISHFUL_SPINNER`, `WISHFUL_MAX_TOKENS`, `WISHFUL_TEMPERATURE`, `WISHFUL_CONTEXT_RADIUS`

---

## 🛡️ Safety Rails: Wishful Isn't _That_ Reckless

Generated code gets AST-scanned to block dangerous patterns: forbidden imports (`os`, `subprocess`, `sys`), `eval()`/`exec()`, unsafe file operations, and system calls.

**Override at your own peril**: `WISHFUL_UNSAFE=1` or `allow_unsafe=True` turns off the guardrails.

---

## 🧪 Testing: Wishes Without Consequences

Need deterministic, offline behavior? Set `WISHFUL_FAKE_LLM=1` and wishful generates placeholder stubs instead of hitting the network. Perfect for CI, unit tests, or when your Wi-Fi is acting up.

```bash
export WISHFUL_FAKE_LLM=1
python my_tests.py  # No API calls, just predictable stubs
```

---

## 🔮 How the Magic Actually Works

1. **Import hook** intercepts `wishful.static.*` and `wishful.dynamic.*` imports
2. **Cache check**: `static` imports load instantly if cached; `dynamic` always regenerates
3. **Context discovery**: Captures nearby comments, code, and registered type schemas
4. **LLM generation**: Generates code via `litellm` based on your import + context
5. **Safety validation**: AST-parsed and checked for dangerous patterns
6. **Execution**: Code is cached to `.wishful/`, compiled, and executed
7. **Transparency**: Just plain Python files. Edit them. Commit them. They're yours.

It's import hooks meets LLMs meets type-aware code generation meets "why didn't this exist already?"

---

## 🎭 Fun with Wishful Thinking

```python
# Cosmic horror stories? Just import it.
from wishful.static.story import cosmic_horror_intro

intro = cosmic_horror_intro(
    setting="a deserted amusement park",
    word_count_at_least=100
)
print(intro)  # 🎢👻

# Math that writes itself
from wishful.static.numbers import primes_from_to, sum_list

total = sum_list(list=primes_from_to(1, 100))
print(total)  # 1060

# Because who has time to write date parsers?
from wishful.static.dates import parse_fuzzy_date

print(parse_fuzzy_date("next Tuesday"))  # Your guess is as good as mine

# Want different results each time? Use dynamic imports!
from wishful.dynamic.jokes import programming_joke

print(programming_joke())  # New joke on every import 🎲
```

---

## 💻 Development: Working with This Repo

This project uses [uv](https://docs.astral.sh/uv/) for blazing-fast Python package management.

### Setup

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repo
git clone https://github.com/pyros-projects/wishful.git
cd wishful

# Install dependencies (uv handles everything)
uv sync
```

### Running Tests

```bash
# Run the full test suite
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_import_hook.py -v

# Run with coverage
uv run pytest --cov=wishful tests/
```

### Running Examples

All examples support `WISHFUL_FAKE_LLM=1` for deterministic testing:

```bash
# Run with fake LLM (no API calls)
WISHFUL_FAKE_LLM=1 uv run python examples/00_quick_start.py

# Run with real LLM (requires API keys)
uv run python examples/00_quick_start.py
```

### Adding Dependencies

```bash
# Add a runtime dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# Update all dependencies
uv lock --upgrade
```

### Project Structure

```
wishful/
├── src/wishful/          # Main package
│   ├── __init__.py       # Public API
│   ├── __main__.py       # CLI interface
│   ├── config.py         # Configuration
│   ├── cache/            # Cache management
│   ├── core/             # Import hooks & discovery
│   ├── llm/              # LLM integration
│   ├── types/            # Type registry system
│   └── safety/           # Safety validation
├── tests/                # Test suite (83 tests, 80% coverage)
├── examples/             # Usage examples
│   ├── 07_typed_outputs.py    # Type registry showcase
│   ├── 08_dynamic_vs_static.py # Static vs dynamic modes
│   └── 09_context_shenanigans.py # Context discovery
└── pyproject.toml        # Project config
```

---

## 🤔 FAQ (Frequently Asked Wishes)

**Q: Is this production-ready?**  
A: Define "production." 🙃

**Q: Can I make the LLM follow a specific style?**  
A: Yes! Use docstrings in `@wishful.type` decorated classes. Want Yoda-speak? Add `"""Written by master yoda from star wars."""` — the LLM will actually do it.

**Q: Do type hints and Pydantic constraints actually work?**  
A: Surprisingly, yes! Field constraints like `min_length=10` or `gt=0` are serialized and sent to the LLM, which respects them.

**Q: What if the LLM generates bad code?**  
A: That's what the cache is for. Check `.wishful/`, tweak it, commit it, and it's locked in.

**Q: Can I use this with OpenAI/Claude/local models?**  
A: Yes! Built on `litellm`, so anything it supports works here.

**Q: What if I import something that doesn't make sense?**  
A: The LLM will do its best. Results may vary. Hilarity may ensue.

**Q: Is this just lazy programming?**  
A: It's not lazy. It's _efficient wishful thinking_. 😎

---

## 📜 License

MIT. 

**Go forth and wish responsibly.** ✨

Your imports will never be the same.
