---
name: wishful
last_updated: 2026-06-11
---

# wishful Strategy

## Target problem

LLMs have made generating code trivial, but generated code is unowned: it gets pasted or cached, and when it fails there is no record of why it exists, what it promised, or how to fix it short of regenerating and hoping. Developers are stuck choosing between hand-writing boilerplate they don't care about and adopting AI output that nobody maintains.

## Our approach

Make the import statement the interface and ownership the product. Wished-for code lands as plain, editable, cached Python in your repo; improvement happens through measured search (variants + fitness + budget + lineage) rather than regenerate-and-hope; and repair is proof-gated and recorded in casefiles — so an import becomes a maintained code object, not a one-shot snippet. Generation is commoditized; accountable maintenance is the territory wishful claims.

Standing requirement: every release is smoke-tested against real model calls — `.env` carries valid credentials for gpt-5.5 — and each smoke run keeps its proof (recorded inputs, outputs, and pass/fail evidence, not just a green checkmark). Fake-LLM tests guard logic; real-model smoke tests with kept evidence guard the product.

## Who it's for

**Primary:** Python developers building tools, prototypes, and data plumbing — they're hiring wishful to turn intent into working utility code without writing or owning boilerplate.

**Secondary:** AI engineers evaluating the active-artifact pattern — they're hiring wishful as the reference demo that generated code can be accountable: failure reports, proof-gated repair, service history.

## Key metrics

- **First-wish success rate** — share of fresh imports that generate, pass safety validation, and run on first call. Not yet instrumented; derivable from cache logs.
- **Cache survival rate** — share of generated modules still in use (or hand-edited and committed) after 30 days, vs deleted or regenerated. Proxy for "code worth owning." Not yet instrumented.
- **Evolve improvement rate** — median fitness improvement across evolve runs. Already recorded in evolution history and explore CSVs.
- **Maintained-import proof** — the concept definition-of-done at function scale: one function that fails, repairs under proof with approval, and carries the casefile. Binary gate, qualitative.
- **PyPI downloads/week** — lagging adoption signal; a rate, so it can regress.

## Tracks

### Core import experience

The magic surface: import hooks, context discovery (002 scope), type registry, safety validation, transparent cache.

_Why it serves the approach:_ zero-ceremony intent-to-code is the wedge; nothing downstream matters if the first wish isn't frictionless.

### Measured search

explore/evolve as the improvement engine: variants, fitness functions, budgets, lineage, and the code-search workbench (spec 003).

_Why it serves the approach:_ replaces regenerate-and-hope with evidence — search beats one-shot generation on the long tail of failures.

### Maintained imports (active artifacts)

The W1–W5 slice: active-import registry, generation casefiles, `report_failure()`, proposal-only repair, then a live Codex runtime. Culminates in the Parser Gauntlet / Four-Act demo.

_Why it serves the approach:_ this is the ownership claim made real — the import that repairs itself under proof is the demo only wishful can give.

## Not working on

- App-level wishes (`wishful app "build me a CRM"`) before function- and feature-level casefiles are boringly reliable.
- Automatic repair apply — proposals never mutate accepted code without proof passing and explicit approval.
- Replacing the lightweight litellm client with an agent runtime for normal `wishful.static.*` generation.
- Tendril/Flock as dependencies — casefiles are the only bridge between projects.
- Dashboards, marketplaces, or platform-building before one maintained import convinces.

## Marketing

**One-liner:** Import your wildest dreams.

**Key message:** Stop writing boilerplate — wish for it instead. And the import didn't just generate code: it became a maintained code object with a service history any qualified mind can pick up.
