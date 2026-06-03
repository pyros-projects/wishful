# Wishful Code Search Workbench: Concept Plan

## Status

This document captures the 2026-06-03 synthesis on why Wishful becomes serious
when it stops competing with one-shot code generation and starts owning bounded
code search.

Read this after:

- `AGENTS.md`
- `docs/specs/001-wishful-evolve/implementation-plan.md`
- `docs/specs/002-wishful-context/product-requirements.md`
- `docs/specs/002-wishful-context/solution-design.md`

Current branch reality:

- `wishful.evolve` has history records and LLM mutation context.
- The public `evolve()` loop is implemented and exported.
- `wishful.context` is specified but not implemented.
- The CLI/dashboard wireframe exists, but evidence/casefile mechanics do not.

## Core Thesis

Wishful's serious wedge is not "generate the missing helper function once."
Modern coding agents can often do that directly.

Wishful becomes valuable when the task has this shape:

```text
target artifact + mutation space + fitness function + budget + accept/rollback
```

That is code search. The developer or coding agent identifies a bounded search
problem, then Wishful runs the repeatable loop, preserves the evidence, and
turns the winner into reusable local code.

Short positioning:

```text
When one-shot codegen plateaus, Wishful keeps going.
```

Agent-facing positioning:

```text
Codie finds the search problem. Wishful runs the search.
```

## Why Not Just Ask A Coding Agent?

For a one-off optimization, a coding agent can loop manually:

1. Inspect slow function.
2. Edit candidate implementation.
3. Run benchmark.
4. Read failures.
5. Edit again.
6. Repeat until better or tired.

That works, but the loop state lives in chat context and reviewer patience. It
is hard to reproduce, hard to batch, hard to inspect later, and easy to lose
across sessions.

Wishful should make the loop infrastructure:

- persistent lineage: every variant, failure, score, and winner is retained
- rerunnable fitness: tests, benchmarks, or evals define "better"
- reusable artifact: the winner becomes the imported function/module
- batch mode: many bounded searches can run under budgets
- review surface: a casefile explains why the winner was allowed to count
- future improvement: the next run starts from known attempts, not amnesia

The analogy is `pytest` versus "Codie, check that this works." Agents can do
manual checks, but durable software work still wants the repeatable harness.

## KG Synthesis Findings

The project-level synthesis from the knowledge graph:

- Acceptance/reviewability: final green checks collapse process quality. Wishful
  should preserve trajectory evidence at function scale, not only the winning
  source.
- Surface-first development: the developer-facing surface is the contract.
  Wishful's contract is the import path, signature, types, context, and fitness
  function.
- Deterministic/probabilistic split: LLM mutation can be probabilistic, but
  critical-path acceptance must depend on deterministic or reproducible sensors
  with declared scope.
- Creative leverage: generate candidates at the level where selection has the
  most downstream control. For Wishful, that level is the importable function or
  small module boundary.
- Proofroom relation: Proofroom asks whether agent work may count at work-unit
  or PR scale. Wishful can ask the same question at generated-function scale and
  feed the answer back into the next generation.

The product primitive this implies:

```text
function with lineage
```

A Wishful function should eventually carry:

- import address
- current source
- declared context
- tests, benchmarks, or evals
- variant history
- failures and error summaries
- winning rationale
- evidence scope
- accept/rollback state

## Demo Selection Filter

Bad demos:

- `generate slugify()`
- `write a CSV parser`
- `make a password validator`
- anything a coding agent can one-shot cleanly

Good demos satisfy all of this:

- one-shot is plausible but not enough
- 20-100 attempts can become meaningfully better
- fitness is cheap enough to run many times
- failures teach the next attempt
- the winner becomes reusable code
- the evidence is interesting to inspect

Kill a demo if:

- the fitness signal is mostly vibes
- the search space is repo-wide rather than function/module-sized
- each evaluation is too expensive for iteration
- one passing implementation is already enough
- the best result cannot be reused as a stable artifact

## Demo Candidates

### 1. NanoGPT/Nanochat Optimizer Or Scheduler Speedrun

Prompt:

```text
Find a task-specialized optimizer or learning-rate schedule that beats tuned
AdamW on this dataset/training setup under fixed budget, seeds, and holdout
checks.
```

Why it is strong:

- One-shot optimizer invention is usually nonsense.
- Repeated measured variants can find local wins.
- The audience immediately understands "beat AdamW on this bounded setup."
- It connects to AutoResearch-style overnight experimentation.

Risks:

- Easy to overfit a tiny benchmark.
- Expensive if the fitness loop is too large.
- Needs tuned AdamW baseline, multiple seeds, and holdout checks or it becomes
  benchmark glitter.

Use this as the sexy flagship after the core harness works.

### 2. Parser Gauntlet

Prompt:

```text
Given 200 ugly real vendor/export files, evolve a parser that maximizes fixture
pass rate while staying readable.
```

Why it is strong:

- Normal coding agents can write parser v1.
- They struggle with the long tail of ugly cases.
- Every failed fixture becomes useful evolutionary pressure.
- Fitness is cheap and deterministic.
- The result is boringly useful to real developers.

This is probably the best first proof demo.

### 3. Hot Path Forge

Prompt:

```text
Make this normalization/scoring/matching function 5x faster without changing
outputs.
```

Fitness:

- property tests for correctness
- benchmark for speed
- optional readability or complexity guard

Why it is strong:

- Shows the difference between "optimize once" and real search.
- Easy to understand in a README or CLI video.
- Can run quickly with fake or local deterministic examples.

### 4. Extractor Or Prompt Arena

Prompt:

```text
Evolve a prompt or small extractor against a labeled eval set.
```

Fitness:

- precision
- recall
- F1
- latency or cost guard

Why it is strong:

- Shows Wishful beyond pure Python algorithms.
- Still has a measurable artifact and stable eval.

Risk:

- If an LLM judge is the primary fitness function, the demo becomes weaker.
  Prefer labeled evals.

### 5. SQL/Rewriter Duel

Prompt:

```text
Generate semantically equivalent query variants and score by correctness plus
runtime on a sample database.
```

Why it is strong:

- Hard to one-shot well.
- Easy to measure.
- Useful in real production-adjacent work.

Risk:

- Needs a safe database fixture and query equivalence checks.

### 6. UI Microcomponent With Visual Fitness

Prompt:

```text
Evolve a small component until Playwright, accessibility, and screenshot checks
pass.
```

Why it is interesting:

- First credible step toward another modality.
- Fitness can combine deterministic checks and visual diffs.

Risk:

- More fragile than code-only demos.
- Should wait until the code-search harness is solid.

## Recommended Demo Order

1. Parser Gauntlet: deterministic, useful, cheap, hard for one-shot agents.
2. Hot Path Forge: obvious value from repeated measured optimization.
3. NanoGPT/Nanochat Optimizer: public "holy shit" demo once overfitting guards
   and casefiles are strong.
4. Extractor/Prompt Arena: shows the artifact model can include prompts.
5. SQL/Rewriter Duel: practical but needs careful fixtures.
6. UI Microcomponent: later, after evidence mechanics can handle non-code
   artifacts cleanly.

## Proposed User Surface

Python surface:

```python
import wishful

@wishful.context(for_="optimizers.WishfulAdam")
def optimizer_context():
    """Beat tuned AdamW on a fixed nanochat run under equal wall-clock budget."""
    return {
        "baseline": "AdamW",
        "metrics": ["val_loss", "time_to_threshold", "stability"],
        "seeds": [1, 2, 3, 4, 5],
        "holdout": "heldout_training_config",
    }

result = wishful.evolve(
    "optimizers.WishfulAdam",
    fitness=score_optimizer,
    generations=30,
    variants=8,
    budget="overnight",
    evidence=True,
)

result.accept()
```

CLI surface:

```bash
uv run wishful evolve optimizers.WishfulAdam \
  --fitness benchmarks/optimizer.py:score_optimizer \
  --generations 30 \
  --variants 8 \
  --casefile

uv run wishful inspect optimizers.WishfulAdam
uv run wishful diff optimizers.WishfulAdam --run latest
uv run wishful accept optimizers.WishfulAdam --run latest
uv run wishful rollback optimizers.WishfulAdam --to previous
```

The CLI should not be dashboard-first. It should expose the evidence model first.

## Evidence Casefile

Minimal casefile directory:

```text
.wishful/evidence/
  optimizers.WishfulAdam/
    2026-06-03T21-42-10Z/
      casefile.json
      casefile.md
      config.json
      winner.py
      variants/
        gen-001-var-001.py
        gen-001-var-002.py
      scores.csv
      failures.md
```

`casefile.json` is for tools. `casefile.md` is for humans.

The casefile should answer:

- What target was evolved?
- What context was attached?
- What fitness function was used?
- What budget was spent?
- Which variants were tried?
- Which variants failed and why?
- Which variant won?
- What evidence supports the winner?
- What known blind spots remain?
- Was the winner accepted into the cache or only proposed?

Recommended default:

- `evolve(..., evidence=True)` writes a casefile every run.
- Winner is not final until accepted when the run is high-risk.
- Low-risk compatibility with `explore()` can still auto-cache the winner.

## Implementation Path

### Phase 0: Finish Existing Branch Spine

Do not start with dashboard work.

Complete:

- `docs/specs/001-wishful-evolve/implementation-plan.md` Phase 3: public
  `evolve()` loop
- Phase 4: public API exports
- Phase 5: example/docs

Then complete:

- `docs/specs/002-wishful-context/implementation-plan.md`
- `@wishful.context` registry and evolve integration

### Phase 1: Evidence-First Evolve Result

Add an `EvolutionResult` or equivalent return object that exposes:

- target
- winner
- history
- best_score
- casefile_path
- accepted flag
- `accept()`
- `rollback()` or companion CLI rollback

Keep this minimal. The point is to stop losing lineage.

### Phase 2: Casefile Writer

Implement a deterministic local writer for:

- JSON casefile
- Markdown summary
- winner source
- variant sources
- score table
- failure summaries

This can be local filesystem only. No server, no dashboard.

### Phase 3: CLI Evidence Surface

Add commands in this order:

1. `wishful evolve`
2. `wishful inspect`
3. `wishful diff`
4. `wishful accept`
5. `wishful rollback`

The commands should make a terminal session compelling before any GUI exists.

### Phase 4: Demo Pack

Create examples under `examples/` or a dedicated `demos/` directory:

- parser gauntlet
- hot path forge
- nanochat optimizer once stable

Each demo needs:

- baseline
- fitness function
- expected run command
- expected casefile screenshot/snippet
- explanation of why one-shot agents struggle

### Phase 5: Batch And Budget Controls

Only after one-target evolution feels good:

- per-run budgets
- variant/generation caps
- timeout per variant
- run queue
- overnight mode
- resume interrupted run

### Phase 6: Dashboard

The existing Excalidraw dashboard should wait until the CLI evidence model is
real. The dashboard should visualize casefiles, not invent a separate state
model.

## Acceptance Criteria For The Product Direction

Wishful has crossed from joke to serious when:

- a user can define a target and fitness function in under five minutes
- Wishful can run many variants without chat supervision
- the winner is inspectable as normal Python code
- the evidence explains why the winner won
- failures are preserved and reused
- rerunning the same case is reproducible enough to review
- a coding agent would prefer using Wishful for bounded searches instead of
  manually looping in chat

## Open Decisions For The Next Session

1. Should `evolve()` auto-cache winners by default, or require explicit
   `accept()` once evidence exists?
2. Should `fitness` return only a float, or a richer object with metrics and
   notes?
3. Should `@wishful.context` allow returning structured data, or only source and
   docstring for v1?
4. Should casefiles live under `.wishful/evidence/` or `.wishful/runs/`?
5. Should demos live in `examples/` or `demos/`?
6. Which first flagship demo do we build: parser gauntlet or hot path forge?

## Restart Checklist

When resuming this work:

```bash
cd /home/pyro/projects/private/wishful
git switch feat/001-wishful-evolve
uv sync
WISHFUL_FAKE_LLM=1 uv run pytest tests/test_evolve.py -v
```

Then read:

1. `AGENTS.md`
2. `docs/specs/001-wishful-evolve/implementation-plan.md`
3. `docs/specs/002-wishful-context/implementation-plan.md`
4. this file

Start by finishing the public `evolve()` loop before touching casefiles,
CLI, demos, or dashboard work.
