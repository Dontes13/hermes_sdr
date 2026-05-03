from rich.console import Console
from rich.panel import Panel

TIER_COLORS = {1: "magenta", 2: "blue", 3: "green", 4: "yellow", 5: "white"}


def render_draft_panel(console: Console, lead: dict, result) -> None:
    """Pretty-print a draft email as a Rich panel."""
    tier = result.hook_tier_used
    color = TIER_COLORS.get(tier, "white")

    header = (
        f"[bold]{lead['company']}[/bold] — {lead['city']}  "
        f"[{color}]T{tier}[/{color}]"
    )
    body = f"[bold]Subject:[/bold] {result.subject}\n\n{result.body}"
    footer = (
        f"Tier {tier} | Hook: {result.hook_text}\n"
        f"Rationale: {result.hook_rationale}"
    )

    console.print(
        Panel(
            body,
            title=header,
            subtitle=footer,
            border_style=color,
            padding=(1, 2),
        )
    )
