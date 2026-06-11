---
title: Security hardening needs a false-positive review, not just bypass-hunting
date: 2026-06-11
category: docs/solutions/best-practices
module: safety
problem_type: best_practice
component: security
severity: high
applies_when:
  - "Tightening a blocklist/validator against demonstrated exploits"
  - "An adversarial review pass found and you closed bypasses in input validation"
tags: [security, validator, code-review, false-positives, blocklist, adversarial-review]
---

# Security hardening needs a false-positive review, not just bypass-hunting

## Context

While hardening wishful's AST safety validator, four rounds of adversarial
review found real RCE gadget bypasses (`__subclasses__`/`__globals__` chains,
`getattr(o, 'sy'+'stem')`, `ns['__builtins__']['eval']`). Each round I tightened
the blocklist to close them — e.g. *block any `getattr` whose attribute name is
not a literal*, and *block any subscript whose key is named after a builtin*
(`'eval'`, `'system'`, …).

Those rules closed the gadgets. They also broke ordinary generated code: by
default (`allow_unsafe=False`) the validator now rejected `getattr(obj, field)`,
`{f: getattr(o, f) for f in fields}`, `config['system']`, and `row['eval']` —
some of the most common idioms an LLM emits. The whole point of the library
(generate working code) was quietly broken for a large class of wishes.

**The four adversarial workflows never caught this.** They were all pointed the
same direction — *find a way IN*. None asked *what legitimate code does this
newly reject?* A later formal multi-persona code review (adversarial reviewer on
usability/contract impact, plus correctness and maintainability) caught it
immediately.

## Guidance

**When you tighten a blocklist against an exploit, run a paired false-positive
review before shipping.** Bypass-hunting and over-block-hunting are *different
review directions* and a finding in one says nothing about the other:

- *Bypass-hunting* (does anything dangerous still get through?) → keeps you safe.
- *Over-block-hunting* (does any common, benign pattern now get rejected?) →
  keeps you usable.

For input validation specifically, the cheap concrete check is: **before/after,
run the validator over a corpus of ordinary legitimate inputs and diff the
pass/fail set.** Anything that newly fails is a regression to weigh against the
exploit you closed.

## Why This Matters

A validator that blocks 100% of attacks and 20% of legitimate inputs is worse
than useless for a tool whose job is to *accept* generated code — it converts
the product's core action into a coin flip, and users reach for the global
`allow_unsafe` escape hatch (disabling *all* checks) just to get work done, which
is strictly worse than the narrow residual you were trying to avoid.

The deeper trap: a blanket rule (*block all non-literal `getattr`*) feels like
strong security, but a blocklist over a language as expressive as Python cannot
distinguish `getattr(obj, field)` from `getattr(obj, evil_var)` at AST time. When
the safe and unsafe forms are syntactically identical, blocking the form blocks
both. The honest resolution is to block only what is *unambiguously* dangerous
(forbidden **literal** names, the `__builtins__`/`globals()`/`vars()`/`locals()`
targets) and accept the ambiguous/computed form as a **documented residual** —
consistent with framing the validator as a best-effort blocklist, not a sandbox.
See [[ast-validator-not-a-sandbox]].

## When to Apply

- After any commit that adds or tightens rules in a validator, sanitizer, linter,
  or auth filter in response to a discovered bypass.
- Whenever a "block all X that isn't a literal/allowlisted value" rule is
  proposed — that shape almost always over-blocks; check the benign cases first.

## Examples

Over-corrected (blocks the gadget AND the common idiom):

```python
# getattr/setattr/delattr/hasattr with a non-literal name -> hard SecurityError
if not (isinstance(name_node, ast.Constant) and isinstance(name_node.value, str)):
    raise SecurityError("getattr() with a non-literal attribute name is blocked")
# breaks: getattr(obj, field), {f: getattr(o, f) for f in fields}
```

Balanced (blocks the unambiguous case, leaves the ambiguous one a residual):

```python
# Only a forbidden *literal* name is blocked; getattr(obj, variable) is allowed
# (computed access is a documented residual — best-effort blocklist, not a sandbox).
if isinstance(name_node, ast.Constant) and isinstance(name_node.value, str):
    if name_node.value in _FORBIDDEN_GETATTR_NAMES:
        raise SecurityError(f"getattr() for forbidden attribute {name_node.value!r}")
```

The verification that should gate the change — real gadgets still blocked,
benign idioms restored:

```text
must block: getattr(o,'__bases__'); getattr(__builtins__,'eval'); type.__dict__['__subclasses__']; globals()['eval']
must pass : getattr(obj, field); {f: getattr(o,f) for f in fields}; config['system']; row['eval']
```
