---
date: 2026-06-04
topic: codex-sdk-native-integration
status: idea
---

# Codex SDK Native Integration

## Thesis

Wishful should stay the bounded code-search harness. Codex should be the
repo-aware agent that decides where the harness is useful, creates the search
setup, and reviews the evidence afterwards.

Short positioning:

```text
Codex finds the search problem. Wishful runs the search.
```

This keeps Wishful from becoming a thin wrapper around a coding agent while
still letting it benefit from Codex's ability to inspect a repository, reason
about tests, and coordinate multi-step engineering work.

## Why This Fits

Wishful's serious direction is already:

```text
target artifact + mutation space + fitness function + budget + accept/rollback
```

That is a clean boundary between orchestration and search:

- Codex can inspect a repo and identify functions, parsers, prompts, SQL
  rewrites, or hot paths that have measurable improvement potential.
- Codex can draft the fitness harness: fixtures, benchmarks, property tests,
  eval data, and acceptance checks.
- Wishful can run repeated variants under budget and preserve lineage.
- Codex can review the casefile and decide whether the result is credible
  enough to accept, revise, or reject.

## Proposed MVP Surface

Start with opt-in commands rather than changing normal import behavior:

```bash
wishful codex scout
wishful codex harness path.to.function
wishful evolve path.to.function --casefile
wishful codex review .wishful/evidence/path.to.function/latest/casefile.json
```

The first useful flow:

1. `scout` asks Codex to inspect the repository and suggest bounded search
   candidates.
2. `harness` asks Codex to create or refine the fitness function for one target.
3. `evolve` remains Wishful's local measured search loop.
4. `review` asks Codex to summarize the evidence, blind spots, and recommended
   accept/reject decision.

## Non-Goals

- Do not replace `wishful.llm.client` for normal `wishful.static.*` generation.
  Import-time generation should remain lightweight and provider-agnostic.
- Do not let Codex silently edit repo files during `import wishful.static.*`.
  Repo-wide agent behavior should be explicit and command-driven.
- Do not build a dashboard first. The valuable primitive is still the evidence
  casefile and accept/rollback loop.

## Product Risks

- The integration becomes too broad and turns Wishful into "just ask Codex."
- Codex-auth, local app-server state, and sandbox policy add too much setup for
  casual users.
- The review step becomes vibes unless the casefile has deterministic evidence:
  tests, benchmarks, fixture pass rates, or labeled eval metrics.

## Validation Demo

Use a parser gauntlet demo first:

```text
Given a directory of ugly vendor/export fixtures, Codex identifies the parser
target and writes the fitness harness. Wishful evolves parser variants until
fixture pass rate improves. Codex reviews the resulting casefile and explains
whether the winner should be accepted.
```

This is stronger than a simple helper-generation demo because one-shot codegen
can plausibly write parser v1, but repeated measured search is better for the
long tail of failures.

## Open Questions

- Should the Codex integration use the TypeScript SDK, Python SDK, or Codex MCP
  server first?
- Should `wishful codex scout` only report candidates, or also create draft
  harness files behind an approval flag?
- Should Codex review be advisory only, or should it be able to call
  `result.accept()` when evidence crosses a configured threshold?
