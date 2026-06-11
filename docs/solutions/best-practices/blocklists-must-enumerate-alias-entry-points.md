---
title: A safety blocklist must enumerate every entry point to a banned capability, not just the obvious name
date: 2026-06-11
category: docs/solutions/best-practices
module: safety
problem_type: best_practice
component: security
severity: high
applies_when:
  - "Writing or auditing a deny-list that blocks a dangerous capability by name (imports, builtins, syscalls, methods)"
  - "A security review closed a bypass by adding entries to a blocklist"
tags: [security, validator, blocklist, aliases, defense-in-depth, code-review]
---

# A safety blocklist must enumerate every entry point to a banned capability, not just the obvious name

## Context

A review of wishful's AST safety validator found that the import deny-list blocked
`os`, `subprocess`, `sys`, `importlib`, and `ctypes` by name — but with safety ON,
`from posix import system; system('id')` and `import nt` sailed straight through.
`posix` and `nt` are the C-level modules `os` re-exports (`os.system` *is*
`posix.system`); `_posixsubprocess` is the helper `subprocess` calls to `fork_exec`.
The blocklist banned the friendly names and forgot the back doors that reach the
exact same capability. This was a real RCE-class gap — and crucially **not** the
documented aliased/computed-access residual: a plain, AST-visible `import posix`
that the blocklist *claimed* to cover.

The same review surfaced the mirror-image defect. A blanket
`_FORBIDDEN_METHODS = {..., "system", "popen", "spawn"}` rule rejected
`platform.system()` — a legitimate call with nothing to do with `os.system`. So one
deny-list was simultaneously **under-blocking** (missed `posix`) and **over-blocking**
(rejected `platform.system()`).

## Guidance

When you ban a capability with a deny-list, ban every *entry point* to that
capability, not just its canonical name. Reason by capability, then enumerate every
module or name that reaches it:

- **Aliases and re-exports**: `os` ↔ `posix` / `nt`; `subprocess` ↔ `_posixsubprocess`;
  any function exposed under two module paths.
- **Lower-level modules** the banned one is a thin wrapper over.

And treat the deny-list as having two symmetric failure directions — sweep both in
the same audit:

- **Under-block** (a dangerous entry point you forgot to list) → a security hole.
  Hunt aliases, re-exports, and C-level counterparts.
- **Over-block** (a benign name that collides with a banned one) → a usability hole.
  A bare-name ban (`.system` on *any* object) catches `os.system` and
  `platform.system` alike. Prefer banning the dangerous *binding* (the import, the
  unbound `os.` base) over the bare name. See the sibling learning below.

## Why This Matters

A deny-list's security guarantee is only as strong as its enumeration. "We block
os/subprocess" reads as covered — but `os` is a thin Python shim over `posix`, so the
moment a generation imports the C module directly the guarantee is void. AST scanning
sees that import plainly, which makes it a **fix**, not a fundamental limit (unlike
aliased/computed access through value-level indirection, which is a genuine residual —
see below). The over-block half is the same lesson from the other side: a bare
method/attribute-name ban over-reaches because the same word belongs to safe and
unsafe objects alike. Both errors come from reasoning about *names* instead of
*capabilities*.

## When to Apply

- After adding any "block module/function X" rule to a validator, sanitizer, or import filter.
- When a banned stdlib module has a documented C-level counterpart or re-export
  (`os`/`posix`/`nt`, `subprocess`/`_posixsubprocess`, …).
- Whenever a blocklist keys on a bare name (`.system`, `'eval'`) rather than a resolved
  binding — verify that no alias slips past *and* that no benign namesake is caught.

## Examples

Under-block (the gap):

```python
_FORBIDDEN_IMPORTS = {"os", "subprocess", "sys", "importlib", "builtins", "ctypes", ...}
# from posix import system; system('id')  -> PASSED validation (posix never listed)
# import nt          (Windows os alias)   -> PASSED
# import _posixsubprocess                 -> PASSED
```

Closed by enumerating the aliases — a three-entry fix, not a redesign:

```python
_FORBIDDEN_IMPORTS = {"os", "subprocess", "sys", "importlib", "builtins", "ctypes", ...,
                      "posix", "nt", "_posixsubprocess"}  # the C-level back doors
```

Over-block (the mirror defect, found in the same review):

```python
_FORBIDDEN_METHODS = {"write_text", "write_bytes", ..., "system", "popen", "spawn"}
# rejects platform.system()  -- a false positive. os.system is already caught by the
# import ban + the unbound-base check, so the bare-name rule adds no security and only
# over-reaches. Dropping system/popen/spawn restores platform.system() with no new gap.
```

The check that should gate the change — both directions at once:

```text
must block: from posix import system; import nt; import _posixsubprocess; os.system('x')
must pass : platform.system(); ordinary stdlib; getattr(obj, field)
```

## Related

- `security-hardening-needs-a-false-positive-review.md` — the over-block direction. The
  same review found both; these two docs are the symmetric halves of one deny-list
  discipline (enumerate every dangerous entry point; don't ban benign namesakes).
- `[[ast-validator-not-a-sandbox]]` — why the validator terminates on a documented
  residual rather than "zero bypasses." Alias gaps like `posix` are *enumerable* and
  therefore fixable; the residual class (aliased/computed access through value-level
  indirection) is not, which is exactly the line between this learning and that one.
