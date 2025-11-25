

<p align="center">
  <img alt="Wishful Banner" src="docs-site/src/content/imgs/wishful_logo (5).jpg" width="800">
</p>

<p align="center">
  <a href="https://badge.fury.io/py/wishful"><img src="https://badge.fury.io/py/wishful.svg" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://github.com/pyros-projects/wishful"><img src="https://img.shields.io/badge/tests-112%20passed-brightgreen.svg" alt="Tests"></a>
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

## 🔍 Explore: When One Wish Isn't Enough

_Sometimes the genie needs a few tries to get it right._

What if instead of trusting the first implementation, you could generate **multiple variants**, test them all, and keep only the winner? Enter `wishful.explore()`:

```python
import wishful

# Generate 5 implementations, keep the first one that passes
parser = wishful.explore(
    "wishful.static.text.extract_emails",
    variants=5,
    test=lambda fn: fn("test@example.com") == ["test@example.com"]
)

# The winner is cached! Future imports use the proven implementation.
from wishful.static.text import extract_emails  # ← Uses the battle-tested winner
```

**The magic**: `explore()` generates multiple candidates, tests each one, and **caches the winner** to `.wishful/`. Subsequent imports skip the exploration entirely—you get the proven implementation instantly.

### Find the Fastest Implementation

```python
def benchmark_sort(fn):
    import time
    start = time.perf_counter()
    for _ in range(100):
        fn(list(range(1000, 0, -1)))
    return 100 / (time.perf_counter() - start)  # ops/sec

# Generate 10 variants, benchmark each, return the fastest
fastest = wishful.explore(
    "wishful.static.algorithms.sort_list",
    variants=10,
    benchmark=benchmark_sort,
    optimize="fastest"
)

print(fastest.__wishful_metadata__)
# {'variant_index': 7, 'benchmark_score': 814106.86, ...}
```

### Beautiful Progress Display

`explore()` shows a real-time Rich display while it works:

```
╭────────── 🔍 wishful.explore → wishful.static.text.extract_emails ───────────╮
│    Exploring extract_emails ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 3/3 • 0:00:03     │
│  Strategy:  first_passing                                                    │
│  Passed:    2                                                                │
│  Failed:    1                                                                │
│                                   Variants                                   │
│  ┏━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  │
│  ┃    # ┃ Status     ┃    Time ┃ Info                                     ┃  │
│  ┡━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩  │
│  │    0 │ passed     │    1.4s │ def extract_emails(text: str) -> list[st │  │
│  │    1 │ failed     │    0.8s │ def extract_emails(s): return re.findall │  │
│  │    2 │ passed     │    1.2s │ import re  def extract_emails(text): ... │  │
│  └──────┴────────────┴─────────┴──────────────────────────────────────────┘  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

Results are also saved to CSV in `.wishful/_explore/` for downstream analysis. Because data-driven wishful thinking is still wishful thinking. 📊

### Going Deeper: LLMs Judging LLMs

Want to get _really_ wild? Check out `examples/13_explore_advanced.py` for:
- **LLM-as-Judge**: Use `wishful.dynamic` to score code quality
- **Code Golf**: Find the shortest working implementation
- **Self-Improving Loops**: The winner helps evaluate the next round
- **Multi-Objective Optimization**: Speed × brevity × quality

It's turtles all the way down. 🐢

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

_Because even genies need settings._

```python
import wishful

wishful.configure(
    model="openai/gpt-5",          # Switch models - use litellm model IDs (default: "azure/gpt-4.1")
    cache_dir="/tmp/.wishful",     # Cache directory for generated modules (default: ".wishful")
    spinner=False,                 # Show/hide the "generating..." spinner (default: True)
    review=True,                   # Review code before execution (default: False)
    allow_unsafe=False,            # Disable safety checks - dangerous! (default: False)
    temperature=0.7,               # LLM sampling temperature (default: 1.0)
    max_tokens=8000,               # Maximum LLM response tokens (default: 4096)
    debug=True,                    # Enable debug logging (default: False)
    log_level="INFO",              # Logging level: DEBUG, INFO, WARNING, ERROR (default: WARNING)
    log_to_file=True,              # Write logs to cache_dir/_logs/ (default: True)
    system_prompt="Custom prompt", # Override the system prompt for LLM (advanced)
)

# Context radius is configured separately (it likes to be special)
wishful.set_context_radius(6)  # Lines of context around imports AND call sites (default: 3)
```

**All Configuration Options:**

_Your wish, your rules._

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | `"azure/gpt-4.1"` | LLM model identifier (litellm format) |
| `cache_dir` | `str \| Path` | `".wishful"` | Directory for cached generated modules |
| `review` | `bool` | `False` | Prompt for approval before executing generated code |
| `spinner` | `bool` | `True` | Show spinner during LLM generation |
| `allow_unsafe` | `bool` | `False` | Disable safety validation (use with caution!) |
| `temperature` | `float` | `1.0` | LLM sampling temperature (0.0-2.0) |
| `max_tokens` | `int` | `4096` | Maximum tokens for LLM response |
| `debug` | `bool` | `False` | Enable debug mode (sets log_level to DEBUG) |
| `log_level` | `str` | `"WARNING"` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `log_to_file` | `bool` | `True` | Write logs to `{cache_dir}/_logs/` |
| `system_prompt` | `str` | _(see source)_ | Custom system prompt for LLM (advanced) |

**Environment Variables:**

All settings can also be configured via environment variables:

- `WISHFUL_MODEL` or `DEFAULT_MODEL` - LLM model identifier
- `WISHFUL_CACHE_DIR` - Cache directory path
- `WISHFUL_REVIEW` - Set to `"1"` to enable review mode
- `WISHFUL_DEBUG` - Set to `"1"` to enable debug mode
- `WISHFUL_UNSAFE` - Set to `"1"` to disable safety checks
- `WISHFUL_SPINNER` - Set to `"0"` to disable spinner
- `WISHFUL_MAX_TOKENS` - Maximum tokens (integer)
- `WISHFUL_TEMPERATURE` - Sampling temperature (float)
- `WISHFUL_CONTEXT_RADIUS` - Context lines around imports and call sites (integer)
- `WISHFUL_LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `WISHFUL_LOG_TO_FILE` - Set to `"0"` to disable file logging
- `WISHFUL_SYSTEM_PROMPT` - Custom system prompt
- `WISHFUL_FAKE_LLM` - Set to `"1"` for deterministic stub generation (testing)

---

## 🛡️ Safety Rails: Wishful Isn't _That_ Reckless

Generated code gets AST-scanned to block dangerous patterns: forbidden imports (`os`, `subprocess`, `sys`), `eval()`/`exec()`, unsafe file operations, and system calls.

**Override at your own peril**: `WISHFUL_UNSAFE=1` or `allow_unsafe=True` turns off the guardrails. We won't judge. (We totally will.)

---

## 🧪 Testing: Wishes Without Consequences

Need deterministic, offline behavior? Set `WISHFUL_FAKE_LLM=1` and wishful generates placeholder stubs instead of hitting the network. Perfect for CI, unit tests, or when your Wi-Fi is acting up.

```bash
export WISHFUL_FAKE_LLM=1
python my_tests.py  # No API calls, just predictable stubs
```

---

## 🔮 How the Magic Actually Works

_Spoiler: it's not actual magic. Or is it?_

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
# The key: import the MODULE, not individual functions!
import wishful
import wishful.dynamic.jokes

# Each function CALL triggers fresh regeneration with runtime context
print(wishful.dynamic.jokes.programming_joke())  # Fresh joke!
print(wishful.dynamic.jokes.programming_joke())  # Different joke! 🎲
print(wishful.dynamic.jokes.programming_joke())  # Another new joke!

# Alternative: use wishful.reimport() to force a fresh module load
jokes = wishful.reimport('wishful.dynamic.jokes')
print(jokes.programming_joke())  # Also regenerates!

# Why does this matter?
# ✓ DO:   import wishful.dynamic.jokes
#         wishful.dynamic.jokes.my_func()  # Regenerates on each call
# ✓ DO:   wishful.reimport('wishful.dynamic.jokes')  # Forces fresh import
# ✗ DON'T: from wishful.dynamic.jokes import my_func
#          my_func()  # This binds once and won't regenerate!
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
│   ├── llm/              # LLM integration (sync + async)
│   ├── types/            # Type registry system
│   ├── explore/          # Multi-variant generation & selection
│   └── safety/           # Safety validation
├── tests/                # Test suite (112 tests)
├── examples/             # Usage examples
│   ├── 07_typed_outputs.py    # Type registry showcase
│   ├── 08_dynamic_vs_static.py # Static vs dynamic modes
│   ├── 09_context_shenanigans.py # Context discovery
│   ├── 12_explore.py          # Multi-variant exploration
│   └── 13_explore_advanced.py # LLM-as-judge, self-improving loops
└── pyproject.toml        # Project config
```

---

## 🤔 FAQ (Frequently Asked Wishes)

**Q: Is this production-ready?**  
A: Define "production." 🙃 (But seriously: the cache gives you plain Python files you can review, edit, and commit. So... maybe?)

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

**Q: What if the LLM generates multiple bad implementations?**  
A: That's what `wishful.explore()` is for! Generate 5-10 variants, test each one, keep the winner. It's like having a code review, but automated and with more variants than your team has patience for.

**Q: Does explore() cache the winning implementation?**  
A: Yes! The winning variant gets cached to `.wishful/` just like a regular import. Future imports use the proven winner—no re-exploration needed.

---

## 📜 License

MIT. 

**Go forth and wish responsibly.** ✨

Your imports will never be the same.
