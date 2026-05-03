import sys
import argparse

from agent.src.config import settings  # noqa: F401 — loads .env before anything else

from agent.src.clients.supabase_client import supabase
from agent.src.functions.draft import draft
from scripts import render_draft_panel

from rich.console import Console

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="Redraft email for a lead")
    parser.add_argument("lead_id")
    args = parser.parse_args()

    # Verify lead exists and has intel
    lead_resp = (
        supabase.table("leads")
        .select("*")
        .eq("id", args.lead_id)
        .single()
        .execute()
    )
    lead = lead_resp.data
    intel = lead.get("intel_json") or {}

    if not intel or intel == {}:
        console.print(
            "[bold red]Error:[/bold red] Lead has no intel data. "
            "Run enrich first."
        )
        sys.exit(1)

    while True:
        result = draft(args.lead_id)
        # Reload lead after draft (status may have changed)
        lead_resp = (
            supabase.table("leads")
            .select("*")
            .eq("id", args.lead_id)
            .single()
            .execute()
        )
        lead = lead_resp.data
        render_draft_panel(console, lead, result)

        answer = input("\nRedraft again? (y/n): ").strip().lower()
        if answer != "y":
            break


if __name__ == "__main__":
    main()
