import sys
import argparse

from agent.src.config import settings  # noqa: F401 — loads .env before anything else

from agent.src.clients.supabase_client import supabase

from rich.console import Console

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset database (delete leads and messages)"
    )
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    if not args.confirm:
        console.print(
            "[bold red]Error:[/bold red] Pass --confirm to reset the database."
        )
        sys.exit(1)

    # Delete messages first (explicit), then leads
    # supabase-py requires a filter for delete — use a condition that matches all rows
    msg_resp = (
        supabase.table("messages")
        .delete()
        .gte("created_at", "1970-01-01")
        .execute()
    )
    msg_count = len(msg_resp.data) if msg_resp.data else 0

    lead_resp = (
        supabase.table("leads")
        .delete()
        .gte("created_at", "1970-01-01")
        .execute()
    )
    lead_count = len(lead_resp.data) if lead_resp.data else 0

    # Clear the poll cursor. Without this, the cursor stays past the
    # old send/reply timestamps while the DB has no thread state to match
    # against — any replies arriving before the next reset would be
    # silently skipped on poll. Inbox_id is preserved so we keep the
    # same AgentMail inbox across resets.
    supabase.table("agentmail_sync").update({"last_polled_at": None}).eq(
        "id", 1
    ).execute()

    console.print(f"Deleted {msg_count} messages, {lead_count} leads.")
    console.print("[dim]Cleared agentmail_sync.last_polled_at.[/dim]")
    console.print("[dim]Config table untouched.[/dim]")


if __name__ == "__main__":
    main()
