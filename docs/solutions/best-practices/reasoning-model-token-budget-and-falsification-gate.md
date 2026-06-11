---
title: Reasoning-model token budgets and the falsification gate for LLM integrations
date: 2026-06-11
category: docs/solutions/best-practices
module: llm
problem_type: best_practice
component: integration
severity: high
applies_when:
  - "An LLM integration returns empty or truncated output from a reasoning model (o-series, gpt-5.x)"
  - "A release/plan depends on a load-bearing bet about an external dependency (a version bump fixes X)"
tags: [llm, reasoning-models, max-tokens, gpt-5-5, litellm, falsification, planning]
---

# Reasoning-model token budgets and the falsification gate for LLM integrations

## Context

During the wishful 0.3.0 release, real-model smoke runs against `openai/gpt-5.5`
failed in three ways that all looked different: empty content
(`LLM returned empty content`), truncated output that failed AST validation
(`invalid syntax after a retry`), and — separately — an interactive example
EOFError. The release plan had pre-registered a single bet: *"the failures are
caused by an old `litellm` floor that predates gpt-5.5; bumping it will fix
them."* A dedicated plan step (U1a) tested that bet against the real model
**before** building the rest of the release on top of it.

## Guidance

**1. Reasoning models need a generous `max_tokens`, and the symptom is empty or
truncated output — not an error.** Reasoning models (o-series, gpt-5.x) spend
part of the completion-token budget on hidden reasoning tokens. With a small cap
(wishful defaulted to `4096`), the budget is exhausted on reasoning and little or
nothing is left for the visible output:

- budget fully spent on reasoning → **empty content**
- budget nearly spent → **truncated / syntactically-invalid output**

The fix was raising the default to `16384`. `litellm` maps `max_tokens` to
`max_completion_tokens` for these models, and that cap *includes* the reasoning
tokens — so it must be sized for reasoning + output, not output alone.

```python
# config.py — default that works for reasoning models
max_tokens: int = field(
    default_factory=lambda: int(os.getenv("WISHFUL_MAX_TOKENS", "16384"))
)
```

**2. Pre-register the load-bearing bet and falsify it first.** The release plan
named its assumption explicitly and tested it in isolation before depending on
it. That step paid off: the bump was **necessary but not sufficient** — the empty
content persisted until `max_tokens` was raised. Testing the bet last (at the
release gate, after building everything) would have produced a deadlocked gate at
maximum sunk cost.

## Why This Matters

The two failure modes (empty vs truncated) looked like two different bugs and
invited two different fixes; they had one root cause. And the obvious fix (the
dependency bump) was real but incomplete. A plan that builds on an unverified
"the bump fixes it" assumption only discovers the gap at the end. A pre-registered
bet plus an early falsification step converts an end-of-project surprise into a
one-session experiment — and the diagnostic error message itself can encode the
real fix so the next person doesn't re-derive it:

```python
raise GenerationError(
    f"{settings.model} returned empty content after 2 attempts. "
    f"If this is a reasoning model, raise max_tokens (currently {settings.max_tokens}) "
    f"or set WISHFUL_TEMPERATURE — reasoning models can spend the whole budget "
    f"on hidden reasoning tokens and return nothing."
)
```

## When to Apply

- Any LLM integration that targets reasoning models, or whose default `max_tokens`
  was chosen for older chat models. Size the cap for reasoning + output and make
  it configurable.
- Any plan whose success hinges on an external dependency behaving a certain way
  ("upgrading X fixes Y"). Name the bet, and add an early step that tests it
  against reality before the rest of the work depends on it.

## Examples

Before (chat-model default, fails on gpt-5.5):

```python
max_tokens = int(os.getenv("WISHFUL_MAX_TOKENS", "4096"))   # empty/truncated output
```

After (reasoning-aware default + retry-then-diagnose):

```python
max_tokens = int(os.getenv("WISHFUL_MAX_TOKENS", "16384"))
# empty content retries once, then raises GenerationError naming the model and
# the reasoning-token cause (see llm/client.py)
```

Falsification-gate shape in the plan:

```text
KTD: "the litellm bump fixes empty content" — UNVERIFIED bet.
U1a: re-run the failing cases against the real model right after the bump,
     BEFORE building the rest. Record the outcome:
       (a) bump alone fixes it -> proceed
       (b) still failing      -> apply the max_tokens fallback (what happened)
       (c) different cause     -> re-plan
```
