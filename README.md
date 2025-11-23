# wishful 🪄

> _"Code so good, you'd think it was wishful thinking"_

Stop writing boilerplate. Start wishing for it instead.

**wishful** turns your wildest import dreams into reality. Just write the import you _wish_ existed, and an LLM conjures up the code on the spot. The first run? Pure magic. Every run after? Blazing fast, because it's cached like real Python.

Think of it as **wishful thinking, but for imports**. The kind that actually works.

## ✨ Quick Wish

**1. Install the dream**

```bash
pip install wishful
```

**2. Set your credentials** (litellm reads the usual suspects)

Export them or toss them in a `.env` file:


```bash
export OPENAI_API_KEY=... 
export DEFAULT_MODEL=azure/gpt-4.1
``

or

```bash
export AZURE_API_KEY=...
export AZURE_API_BASE=https://<your-endpoint>.openai.azure.com/
export AZURE_API_VERSION=2025-04-01-preview
export DEFAULT_MODEL=azure/gpt-4.1
```

or any provider else supported by litellm





**3. Import your wildest fantasies**

```python
from wishful.text import extract_emails
from wishful.dates import to_yyyy_mm_dd

raw = "Contact us at team@example.com or sales@demo.dev"
print(extract_emails(raw))  # ['team@example.com', 'sales@demo.dev']
print(to_yyyy_mm_dd("31.12.2025"))  # '2025-12-31'
```

**What just happened?**

- **First import**: wishful waves its wand 🪄, asks the LLM to write `extract_emails` and `to_yyyy_mm_dd`, validates the code for safety, and caches it to `.wishful/text.py` and `.wishful/dates.py`.
- **Every subsequent run**: instant. Just regular Python imports. No latency, no drama, no API calls.

It's like having a junior dev who never sleeps and always delivers exactly what you asked for (well, _almost_ always).

---

## 🎯 Wishful Guidance: Help the AI Read Your Mind

Want better results? Drop hints. Literal comments. wishful reads the code _around_ your import and forwards that context to the LLM.

```python
# desired: parse standard nginx combined logs into list of dicts
from wishful.logs import parse_nginx_logs

records = parse_nginx_logs(Path("/var/log/nginx/access.log").read_text())
```

The AI sees your comment and knows _exactly_ what you're after. It's like pair programming, but your partner is a disembodied intelligence with questionable opinions about semicolons.

---

## 🗄️ Cache Ops: Because Sometimes Wishes Need Revising

### Python API

```python
import wishful

# See what you've wished for
wishful.inspect_cache()   # ['.wishful/text.py', '.wishful/dates.py']

# Regret a wish? Regenerate it
wishful.regenerate("wishful.text")  # Next import re-generates from scratch

# Nuclear option: forget everything
wishful.clear_cache()  # Deletes the entire .wishful/ directory
```

### CLI Commands

wishful comes with a command-line interface for managing your cache:

```bash
# View all cached modules
wishful inspect

# Clear the entire cache
wishful clear

# Regenerate a specific module
wishful regen wishful.text
```

The cache is just regular Python files in `.wishful/`. Want to tweak the generated code? Edit it directly. It's your wish, after all.

---

## ⚙️ Configuration: Fine-Tune Your Wishes

```python
import wishful

wishful.configure(
    model="gpt-4o-mini",        # Switch models like changing channels
    cache_dir="/tmp/.wishful",  # Hide your wishes somewhere else
    spinner=False,              # Silence the "generating..." spinner
    review=True,                # Paranoid? Review code before it runs
    # Control how much nearby code is sent to the LLM for context
    # (applies to both import lines and call sites)
    # or set via WISHFUL_CONTEXT_RADIUS env var.
    # Example: wishful.set_context_radius(6)
    allow_unsafe=False,         # Keep the safety rails ON (recommended)
)
```

### Environment Variables (for the env-obsessed)

Set these in your shell or `.env` file:

- `WISHFUL_MODEL` / `DEFAULT_MODEL` — which AI overlord to summon
- `WISHFUL_CACHE_DIR` — where to stash generated wishes (default: `.wishful`)
- `WISHFUL_REVIEW` — set to `1` to manually approve every wish (trust issues?)
- `WISHFUL_DEBUG` — verbose logging for when things go sideways
- `WISHFUL_UNSAFE` — set to `1` to disable safety checks (⚠️ danger zone)
- `WISHFUL_SPINNER` — set to `0` to disable the fancy spinner
- `WISHFUL_MAX_TOKENS` — cap the LLM's verbosity (default: 800)
- `WISHFUL_TEMPERATURE` — creativity dial (default: 0 = boring but safe)
- `WISHFUL_CONTEXT_RADIUS` — how many surrounding lines to capture for context (default: 3). Also applied to call sites of requested symbols.

Context harvesting
- wishful forwards code/comments around the import line **and** around call sites of the requested symbols. The number of lines captured on each side is controlled by `wishful.set_context_radius(n)` or `WISHFUL_CONTEXT_RADIUS`.

---

## 🛡️ Safety Rails: Wishful Isn't _That_ Reckless

Generated code gets AST-scanned to block obviously dangerous patterns:

- ❌ Imports like `os`, `subprocess`, `sys`
- ❌ Calls to `eval()` or `exec()`
- ❌ `open()` in write/append mode
- ❌ Shenanigans like `os.system()` or `subprocess.call()`

**Override at your own peril**: `WISHFUL_UNSAFE=1` or `allow_unsafe=True` turns off the guardrails.

---

## 🧪 Testing: Wishes Without Consequences

Need deterministic, offline behavior? Set `WISHFUL_FAKE_LLM=1` and wishful will generate placeholder stub functions instead of hitting the network.

Perfect for CI, unit tests, or when your Wi-Fi is acting up.

```bash
export WISHFUL_FAKE_LLM=1
python my_tests.py  # No API calls, just predictable stubs
```

---

## 🔮 How the Magic Actually Works

Here's the 30-second version:

1. **Import hook**: wishful installs a `MagicFinder` on `sys.meta_path` that intercepts `wishful.*` imports.
2. **Cache check**: If `.wishful/<module>.py` exists, it loads instantly. No AI needed.
3. **LLM generation**: If not cached, wishful calls the LLM (via `litellm`) to generate the code based on your import and surrounding context.
4. **Validation**: The generated code is AST-parsed and safety-checked (unless you disabled that like a madman).
5. **Execution**: Code is written to `.wishful/`, compiled, and executed as the import result.
6. **Transparency**: The cache is just plain Python files. Edit them. Commit them. They're yours.

It's import hooks meets LLMs meets "why didn't this exist already?"

---

## 🎭 Fun with Wishful Thinking

```python
# Need some cosmic horror? Just wish for it.
from wishful.story import cosmic_horror_intro

intro = cosmic_horror_intro(
    setting="a deserted amusement park",
    word_count_at_least=100
)
print(intro)  # 🎢👻

# Math that writes itself
from wishful.numbers import primes_from_to, sum_list

total = sum_list(list=primes_from_to(1, 100))
print(total)  # 1060 (probably)

# Because who has time to write date parsers?
from wishful.dates import parse_fuzzy_date

print(parse_fuzzy_date("next Tuesday"))  # Your guess is as good as mine
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
│   ├── core/             # Import hooks
│   ├── llm/              # LLM integration
│   └── safety/           # Safety validation
├── tests/                # Test suite
├── examples/             # Usage examples
└── pyproject.toml        # Project config
```

---

## 🤔 FAQ (Frequently Asked Wishes)

**Q: Is this production-ready?**  
A: Define "production." 🙃

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

MIT. Wish responsibly.

**Go forth and wish.** ✨

Your imports will never be the same.
