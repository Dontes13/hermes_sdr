import sys
import argparse

from agent.src.config import settings  # noqa: F401 — loads .env before anything else

from agent.src.clients.supabase_client import supabase
from agent.src.functions.draft import draft
from agent.src.functions.enrich import enrich
from agent.src.functions.prospect import prospect
from scripts import render_draft_panel

from rich.console import Console
from rich.table import Table

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="Helios SDR Phase 1 Test")
    parser.add_argument("--city", required=True)
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()

    console.rule(f"[bold]PHASE 1 TEST — {args.city}, {args.count} leads[/bold]")

    # Step 1: Prospect
    console.print("\n[bold cyan]Step 1: Prospecting...[/bold cyan]")
    inserted_ids = prospect(args.city, max_leads=args.count)
    console.print(f"  Inserted {len(inserted_ids)} leads\n")

    if not inserted_ids:
        console.print(
            "[bold red]No leads inserted. "
            "Check Places API key and city name.[/bold red]"
        )
        sys.exit(0)

    # Step 2: Enrich each lead
    console.print("[bold cyan]Step 2: Enriching...[/bold cyan]")
    leads: dict[str, dict] = {}
    for lead_id in inserted_ids:
        enrich(lead_id)
        resp = (
            supabase.table("leads")
            .select("*")
            .eq("id", lead_id)
            .single()
            .execute()
        )
        lead = resp.data
        leads[lead_id] = lead
        status_color = "green" if lead["status"] == "enriched" else "red"
        console.print(
            f"  {lead['company']}: [{status_color}]{lead['status']}[/{status_color}]"
        )
    console.print()

    # Step 3: Draft emails for enriched leads
    console.print("[bold cyan]Step 3: Drafting...[/bold cyan]\n")
    draft_results: dict[str, object] = {}
    for lead_id, lead in leads.items():
        if lead["status"] != "enriched":
            continue
        result = draft(lead_id)
        draft_results[lead_id] = result
        render_draft_panel(console, lead, result)

    # Summary table
    console.print()
    console.rule("[bold]Summary[/bold]")
    table = Table()
    table.add_column("Company")
    table.add_column("Status")
    table.add_column("Hook Tier")
    table.add_column("Email Found")

    for lead_id in inserted_ids:
        lead = leads[lead_id]
        dr = draft_results.get(lead_id)
        tier_str = str(dr.hook_tier_used) if dr else "—"
        email_found = "Y" if lead.get("email") else "N"
        table.add_row(lead["company"], lead["status"], tier_str, email_found)

    console.print(table)
    console.print()


if __name__ == "__main__":
    main()
