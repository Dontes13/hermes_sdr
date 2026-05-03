"""Smoke test for the LinkedIn channel.

Usage:
    python scripts/test_linkedin_send.py --lead-id <uuid> --kind invite [--send]
    python scripts/test_linkedin_send.py --lead-id <uuid> --kind dm     [--send]

Drafts a LinkedIn invite or DM for the given lead, prints it to the
terminal, and (if --send is passed) ships it through Unipile.

Requires UNIPILE_API_KEY / UNIPILE_DSN / UNIPILE_ACCOUNT_ID in .env when
--send is used. Drafting only works without those.
"""

import argparse
import sys

from agent.src.config import settings  # noqa: F401 — loads .env first

from rich.console import Console

from agent.src.clients.supabase_client import supabase
from agent.src.exceptions import LinkedInDraftError, SendError
from agent.src.functions.draft_linkedin import draft_for_kind
from agent.src.functions.send_linkedin import send_linkedin

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="LinkedIn channel smoke test")
    parser.add_argument("--lead-id", required=True)
    parser.add_argument("--kind", choices=["invite", "dm"], required=True)
    parser.add_argument(
        "--send",
        action="store_true",
        help="Actually send via Unipile after drafting",
    )
    args = parser.parse_args()

    console.rule(f"[bold]LinkedIn {args.kind} test — lead {args.lead_id}[/bold]")

    try:
        result = draft_for_kind(args.lead_id, args.kind)
    except LinkedInDraftError as e:
        console.print(f"[red]Draft failed:[/red] {e}")
        sys.exit(1)

    console.print(f"\n[cyan]Draft body ({len(result.body)} chars):[/cyan]")
    console.print(result.body)
    console.print(
        f"\n[dim]hook_tier={result.hook_tier_used} · "
        f"hook_text={result.hook_text!r}[/dim]"
    )

    if not args.send:
        console.print(
            "\n[yellow]Pass --send to actually ship via Unipile.[/yellow]"
        )
        return

    # Look up the message we just inserted (the latest pending of this channel).
    channel = "linkedin_invite" if args.kind == "invite" else "linkedin_dm"
    msg = (
        supabase.table("messages")
        .select("id")
        .eq("lead_id", args.lead_id)
        .eq("channel", channel)
        .eq("direction", "outbound")
        .is_("sent_at", "null")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not msg.data:
        console.print("[red]No pending draft found after drafting?[/red]")
        sys.exit(2)

    try:
        send_result = send_linkedin(msg.data[0]["id"])
    except SendError as e:
        console.print(f"[red]Send failed:[/red] {e}")
        sys.exit(3)

    console.print(f"\n[green]Sent.[/green] {send_result}")


if __name__ == "__main__":
    main()
