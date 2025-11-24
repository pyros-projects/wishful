
"""Cosmic horror story that regenerates a new section on every turn."""

import wishful
import wishful.dynamic.story as story
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.text import Text
from rich import box
from rich.align import Align

console = Console()
wishful.configure(spinner=False)
wishful.set_context_radius(10)

# Opening screen
console.clear()
console.print()
console.print(
    Panel(
        Align.center(
            Text.from_markup(
                "[bold red]✦  D R E A D   G P T  ✦[/bold red]\n\n"
                "[dim]Press [bold]Enter[/bold] to continue into the abyss\n"
                " or type [bold red]'exit'[/bold red] to escape[/dim]", justify="center"
            )
        ),
        box=box.DOUBLE,
        border_style="red",
        padding=(1, 2),
    )
)
console.print()

# Generate hooks and let the reader pick the doomed path
def _normalize_hooks(hooks) -> list[str]:
    if isinstance(hooks, str):
        parts = [h.strip("-•* \t") for h in hooks.splitlines()]
        return [p for p in parts if p]
    if isinstance(hooks, (list, tuple)):
        return [str(h).strip() for h in hooks if str(h).strip()]
    return []


with console.status("[bold red]Searching for souls getting screwed by fate...", spinner="dots"):
    list_of_story_hooks = story.cosmic_horror_list_of_story_hooks(
        format="string list",
        min_items=5
    )

hooks = _normalize_hooks(list_of_story_hooks)
if not hooks:
    hooks = ["An Antarctic research outpost that keeps hearing voices in the wind."]

console.print("[bold red]Choose your doom:[/bold red]\n")
for idx, hook in enumerate(hooks, 1):
    console.print(f"[dim]{idx}. {hook}[/dim]")

choice = Prompt.ask(
    "\nWhich poor soul's story do we turn into horror? Or type your own twisted idea:",
    default="1",
)

chosen_hook = choice.strip()
if choice.isdigit():
    idx = int(choice)
    if 1 <= idx <= len(hooks):
        chosen_hook = hooks[idx - 1]
    else:
        chosen_hook = hooks[0]
elif not chosen_hook:
    chosen_hook = hooks[0]

print(chosen_hook)

# Generate intro with dramatic reveal, using the chosen hook as setting
with console.status("[bold red]The darkness stirs...", spinner="dots"):
    intro = story.cosmic_horror_shortstory_intro(
        format="markdown with title",
        min_length=500,
        style="cormac mccarthy, bleak and haunting",
        setting=chosen_hook,
    )

# Display intro in a panel
console.print(
    Panel(
        Markdown(intro),
        title="[bold red]◈ The Beginning ◈[/bold red]",
        border_style="red",
        box=box.HEAVY,
        padding=(1, 2),
    )
)
console.print()

section_num = 1

story_so_far = intro

while True:
    # Prompt with style
    user_input = Prompt.ask(
        "[dim]Press [bold]Enter[/bold] to continue into the abyss, or type [bold red]'exit'[/bold red] to escape[/dim]",
        default=""
    )
    
    if user_input.lower() == 'exit':
        console.print()
        console.print(
            Panel(
                Align.center(
                    Text("The void remembers...", style="bold dim italic")
                ),
                border_style="dim red",
                box=box.SIMPLE,
            )
        )
        console.print()
        break

    section_num += 1
    
    # Generate next section with animated status
    with console.status(
        f"[bold red]Channeling cosmic dread (Section {section_num})...",
        spinner="aesthetic"
    ):
        # Dynamic proxy forces regeneration on each attribute access
        next_section = story.cosmic_horror_next_section(
            text_so_far=story_so_far,
            min_length=500,
            style="cormac mccarthy, bleak and haunting",
            setting=chosen_hook,
        )
    
    # Display new section in a panel
    console.print()
    console.print(
        Panel(
            Markdown(next_section),
            title=f"[bold red]◈ Descent {section_num} ◈[/bold red]",
            border_style="red",
            box=box.HEAVY,
            padding=(1, 2),
        )
    )
    console.print()
    
    story_so_far += "\n\n" + next_section
