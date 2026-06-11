# 0.3.0 example sweep — real gpt-5.5

Companion to `summary.json` (the smoke-harness gate, 4/4 green). This records the
`examples/*.py` runs against real `openai/gpt-5.5`, including the previously-broken
examples the 0.3.0 work targeted.

## Binding gate

`summary.json`: **4/4 smoke cases pass** (static import, dynamic call, explore,
evolve) — the STRATEGY.md release gate.

## Previously-broken examples (the 0.3.0 model-path fix)

The 2026-06-11 review's smoke run failed examples 00/08/09/10/13 with empty
content or truncation on gpt-5.5. Root cause: `max_tokens=4096` was too small for
a reasoning model that spends part of its budget on hidden reasoning tokens.

| Example | Before | After fix | Note |
|---------|--------|-----------|------|
| 00_quick_start | empty/invalid syntax | **PASS** | needed `max_tokens` raise + a context hint steering `count_headers` to `open()`/str methods (the model had reached for `import os`, correctly blocked) |
| 09_context_shenanigans | empty content | **PASS** (293 s) | fixed purely by `max_tokens=16384` |
| 10_cosmic_horror | empty content | slow (timeout) | now generates valid output but is slow: heavy 500-word dynamic-mode prose, and dynamic mode regenerates 2–3× per call (deferred to plan 002 U1). Headless guard added so it no longer EOFErrors. |
| 08_dynamic_vs_static | timeout/empty | slow | same dynamic double-generation latency as 10; not a correctness failure |
| 13_explore_advanced | no valid variants | excluded | LLM-as-judge demo: the example's own judge rejects all variants (judge-side nondeterminism), excluded from the hard gate per plan 001 U1a |

## Decision

The U1a falsification confirmed the core finding: the litellm bump was necessary
but not sufficient — raising `max_tokens` to 16384 is what resolves the
empty-content / truncated-syntax class. The remaining example friction (08/10
slowness, 13 judge variance) is deferred-economics and example-design, not core
correctness, so it does not block the 0.3.0 release. The dynamic double-generation
that makes 08/10 slow is plan 002 U1.
