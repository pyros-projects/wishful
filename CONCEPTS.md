# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Safety

### Validator
wishful's static safety check over LLM-generated code before it executes: a best-effort deny-list of dangerous imports, builtins, and introspection gadgets — explicitly **not** a sandbox.

Because it scans the AST, it catches direct and literal-form danger (a forbidden import, `eval(...)`, a `__subclasses__` gadget chain) but cannot follow value-level indirection. Its guarantee is the *enumeration* of banned capabilities plus the Review gate, not containment — code it admits still runs with full process privileges. What it admits unsafely splits into two kinds: a Residual (provably uncatchable) versus an enumeration gap (a banned capability reached by an alias the deny-list simply forgot to list — a fixable bug).

### Review gate
The configurable approval step that must pass before any generated code executes, on every generation path. It fails closed: when no interactive prompt is reachable (no terminal or notebook kernel), it raises rather than silently approving or hanging, and an empty/EOF response counts as rejection.

### Residual
A class of bypass the Validator provably cannot detect — aliased or computed access reached through value-level indirection (binding a dangerous builtin to a variable, then calling it through that name) — documented and accepted rather than treated as a defect to fix. Distinct from an enumeration gap, which the deny-list *can* catch once the missing entry point is listed.
