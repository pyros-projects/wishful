"""Example 09: Runtime context shenanigans — dynamic wishes that read their arguments.

Dynamic modules regenerate on every call, and the *call site* — function name,
arguments, even previous outputs you pass back in — becomes prompt context.
This example leans into that: the same wish, steered entirely by kwargs.

Run with: `uv run python examples/09_context_shenanigans.py`
(needs a real LLM; dynamic regeneration is the whole point here)
"""

import wishful

wishful.clear_cache()


# --- One wish, steered by its arguments -------------------------------------
# generate_project_idea doesn't exist anywhere. Each call regenerates it with
# the runtime arguments as context, so the kwargs ARE the spec: topic, which
# sections to include, plan granularity, output format.
from wishful.dynamic.ideas import generate_project_idea

idea1 = generate_project_idea(
    topic="space",
    include_project_brief=True,
    include_plan=True,
    plan_levels=["Milestone", "Story", "Task"],
    format="markdown",
)
print(f"{idea1}")

# --- Feeding outputs back in as context --------------------------------------
# Passing the previous result via old_ideas_to_avoid puts it into the next
# generation's prompt — a poor man's memory, one kwarg deep.
idea2 = generate_project_idea(
    topic="space",
    include_project_brief=True,
    include_plan=True,
    plan_levels=["Milestone", "Story", "Task"],
    format="json",
    old_ideas_to_avoid=[idea1],
)
print(f"{idea2}")
