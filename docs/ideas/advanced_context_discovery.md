# Advanced Context Discovery Ideas

This document brainstorms potential enhancements to wishful's context discovery system beyond the current ±3 line comment extraction.

## Current State

The `discovery.py` module uses stack inspection + `linecache` to:
- Extract function names from import statements via AST parsing
- Grab ±3 lines around the import for comment context
- Forward this to the LLM as hints

**Limitations:**
- Fixed 3-line radius misses broader context
- Only captures raw text comments, not semantic information
- No awareness of type hints, docstrings, or surrounding code structure
- Single discovery strategy (comment-based)

---

## Configurable Context Radius

**Idea**: Allow users to tune the context window size via config or environment variables.

```python
wishful.configure(context_radius=5)  # Grab ±5 lines instead of ±3
# or
export WISHFUL_CONTEXT_RADIUS=10
```

**Benefits:**
- Users with detailed multi-line comments get full context
- Tighter radius for minimal noise in dense files

**Implementation:**
- Add `context_radius: int = 3` to `Settings` in `config.py`
- Pass to `_gather_context_lines()` in `discovery.py`
- Document that larger radius = more LLM tokens consumed

**Gotchas:**
- Very large radius might include unrelated imports or code
- Need to balance signal vs. noise

---

## Type Hint Extraction

**Idea**: Parse type hints from the import statement and surrounding code to give the LLM richer semantic information.

```python
from typing import List, Dict
# desired: extract email addresses
from wishful.text import extract_emails

# Context sent to LLM includes:
# - Function name: extract_emails
# - Comment: "extract email addresses"
# - Inferred return type: List[str] (from usage or annotation)
```

**Approaches:**

### 1. Parse Usage Context
Look at how the imported symbol is used immediately after:
```python
from wishful.utils import parse_date
result: datetime = parse_date("2025-01-01")  # Infer return type is datetime
```

Use AST to walk forward from the import and detect assignments with type annotations.

### 2. Scan for Nearby Type Aliases
```python
EmailList = List[str]
from wishful.emails import extract_all  # Hint: might return EmailList
```

### 3. Extract from Docstrings
If there's a docstring ABOVE the import (rare but possible):
```python
"""
This module needs a function to parse nginx logs.
Expected signature: parse_nginx_logs(text: str) -> List[Dict[str, str]]
"""
from wishful.logs import parse_nginx_logs
```

**Implementation:**
- Extend `discover()` to optionally walk AST nodes after the import
- Add `type_hints: Optional[str]` to `ImportContext`
- Include in LLM prompt: "Expected return type: {type_hints}"

---

## Multi-Strategy Discovery

**Idea**: Support multiple context discovery algorithms and let users choose or combine them.

### Strategy Options:

#### 1. **Comment-Based** (current default)
- Grab ±N lines around import
- Fast, simple, works for most cases

#### 2. **Scope-Aware**
- Capture the entire function/class scope containing the import
- Useful when import is inside a function with rich docstrings/context

```python
def process_logs(log_path: Path):
    """Process nginx access logs and extract IP addresses.
    
    Returns a list of unique IPs sorted by frequency.
    """
    from wishful.logs import extract_ips  # Captures full function context
    return extract_ips(log_path.read_text())
```

#### 3. **Module-Level Docstring**
- Include the importing file's top-level docstring
- Good for domain-specific context

```python
"""
Financial analysis toolkit. All functions handle decimal precision
and return monetary values as Decimal objects.
"""
from wishful.finance import calculate_interest
```

#### 4. **Proximity-Based**
- Look for nearby class/function definitions that might relate
- Example: If importing inside a class method, include class docstring

#### 5. **Comment Block Aggregation**
- Gather ALL comments in the file (or top N) to build domain context
- Useful for files with rich header comments explaining conventions

### Configuration:

```python
wishful.configure(
    discovery_strategy="scope",  # or "comment", "docstring", "proximity"
    # Or combine multiple:
    discovery_strategies=["comment", "docstring"],
)
```

**Implementation:**
- Create `DiscoveryStrategy` protocol/interface
- Implement each as separate class in `discovery.py`
- Chain strategies together (e.g., try scope, fallback to comment)

---

## Enhanced Comment Patterns

**Idea**: Support structured comment formats beyond "desired:".

### Existing Pattern:
```python
# desired: parse nginx logs
from wishful.logs import parse_nginx_logs
```

### New Patterns:

#### Type-Aware Comments:
```python
# @desired(returns=List[str]): extract email addresses from text
from wishful.text import extract_emails
```

#### Multi-Line Specifications:
```python
# desired:
#   parse nginx combined log format
#   return list of dicts with keys: ip, timestamp, method, path, status, size
from wishful.logs import parse_nginx_logs
```

#### Example-Driven:
```python
# example: factorial(5) -> 120
from wishful.math import factorial
```

**Parsing Logic:**
- Extend `_gather_context_lines()` to detect structured markers
- Extract type hints, examples, constraints from formatted comments
- Build richer LLM prompt with "Examples:", "Return Type:", sections

---

## Cross-File Context Resolution

**Idea**: When generating a function, look for related functions in OTHER generated modules for consistency.

**Scenario:**
```python
# File A
from wishful.dates import parse_date

# File B (later)
from wishful.dates import format_date  # Should be consistent with parse_date
```

**Approach:**
- Before generating, check if `.wishful/dates.py` already exists
- Extract function signatures from cached module
- Include in LLM prompt: "Existing functions in this module: parse_date(date_str: str) -> datetime"

**Benefits:**
- Generated code maintains consistent API design
- Avoids conflicting implementations (e.g., different date formats)

**Implementation:**
- In `loader.py`, before calling `generate_module_code()`, read cached source
- Parse with AST to extract function names + signatures
- Pass as `existing_functions: List[FunctionSignature]` to LLM prompt

---

## Interactive Context Enrichment

**Idea**: When context is ambiguous, prompt the user for clarification BEFORE calling the LLM.

**Example:**
```python
from wishful.text import parse  # Ambiguous! Parse what?
```

Wishful could:
1. Detect missing/vague context
2. Prompt: "What should `parse` do? (e.g., 'parse JSON', 'parse CSV', 'parse markdown')"
3. Use answer as context for generation

**Implementation:**
- Add confidence scoring to context discovery
- If confidence < threshold, trigger interactive prompt
- Store user responses in cache metadata for future reference

**Configuration:**
```python
wishful.configure(interactive_context=True)  # Enable prompts
export WISHFUL_INTERACTIVE=1
```

---

## AST-Based Argument Inference

**Idea**: Analyze how the imported function is CALLED to infer parameter names/types.

```python
from wishful.math import calculate
result = calculate(amount=100, rate=0.05, years=10)
# Infer: calculate(amount: float, rate: float, years: int) -> float
```

**Approach:**
- Use AST to find all `Call` nodes invoking the imported symbol
- Extract keyword arguments → parameter names
- Extract positional argument types (if literals or annotated variables)
- Build function signature hint for LLM

**Challenge:**
- Function might be called AFTER import in subsequent lines (need to scan forward)
- Non-trivial to determine types from variables (need deeper analysis)

**Implementation:**
- Extend `discover()` to parse forward in the frame's scope
- Look for `ast.Call` nodes matching the imported name
- Heuristic: scan up to 10 lines forward or until next import/function def

---

## Context Caching & Learning

**Idea**: Remember successful context patterns and reuse them for similar imports.

**Scenario:**
```python
# First time
# desired: parse nginx logs
from wishful.logs import parse_nginx_logs
# LLM generates good code, cached

# Later, in different file
from wishful.logs import parse_apache_logs  # Similar domain!
# System suggests: "Based on parse_nginx_logs, should this also parse logs?"
```

**Implementation:**
- Store context → code mappings in a separate `.wishful/.context_db.json`
- On new import, do fuzzy matching against known patterns
- Augment prompt with: "Similar function parse_nginx_logs does X, you might do Y"

**Benefits:**
- Faster, more consistent generation
- Builds project-specific "memory" of patterns

---

## Package-Level Context Files

**Idea**: Let users provide `.wishful/context.yaml` or `.wishful/context.md` with global hints.

**Example `.wishful/context.yaml`:**
```yaml
global_context: |
  This project is a financial analysis tool.
  All monetary values use Decimal for precision.
  Dates are in ISO 8601 format.

module_hints:
  finance:
    - "Calculate interest using compound formula"
    - "Return Decimal, not float"
  dates:
    - "Parse common formats: YYYY-MM-DD, DD.MM.YYYY, MM/DD/YYYY"
```

**Usage:**
- `discovery.py` reads this file on first import
- Merges global/module-specific context into every LLM prompt
- Users can commit this to version control for team-wide consistency

**Benefits:**
- No need to repeat common context in every file
- Easy to maintain project conventions centrally

---

## IDE Integration Hooks

**Idea**: For editors with type inference (VSCode, PyCharm), extract inferred types from LSP.

**Fantasy Implementation:**
```python
# VSCode knows from context that this should return List[int]
from wishful.math import primes_up_to
result = primes_up_to(100)  # IDE infers List[int]
```

Wishful could query the LSP server for type information and include it in context.

**Challenges:**
- Requires integration with editor-specific APIs
- LSP might not have info until AFTER successful import
- Complex dependency on IDE setup

**Alternative:**
- Use `typing.get_type_hints()` on the importing module after generation
- Validate generated code matches expected types
- Regenerate if mismatch detected

---

## Weighted Context Sources

**Idea**: Assign priority to different context sources and merge them intelligently.

**Priority Hierarchy:**
1. **Explicit type hints** (highest signal)
2. **"desired:" comments** (user intent)
3. **Docstrings** (broad context)
4. **Surrounding code** (usage patterns)
5. **Global context files** (project conventions)

**Implementation:**
- Each discovery strategy returns `(context: str, confidence: float)`
- Merge by priority, with higher-confidence sources first in prompt
- LLM sees: "High confidence: <type hints>, Medium: <comments>, Low: <docstring>"

---

## Summary & Recommendations

**Quick Wins** (low effort, high value):
- [ ] Configurable context radius
- [ ] Enhanced comment patterns (multi-line, structured)
- [ ] Cross-file context (read existing cached modules)

**Medium Complexity:**
- [ ] Type hint extraction from usage
- [ ] Multi-strategy discovery (scope-aware, docstring)
- [ ] Package-level context files

**Advanced/Experimental:**
- [ ] Interactive context enrichment
- [ ] AST-based argument inference
- [ ] Context caching & learning
- [ ] IDE integration hooks

**Next Steps:**
1. Prototype configurable radius (easiest MVP)
2. Add unit tests for new discovery patterns
3. Gather user feedback on which strategies are most valuable
4. Iterate based on real-world usage patterns
