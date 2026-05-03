"""E2E test step 1: send a real cold email to yourself.

Creates a synthetic enriched lead with minimal intel, runs the real
draft() + send() functions, and delivers a cold email via AgentMail
to the given address. Prints the lead_id so you can feed it into
scripts/e2e_check.py after replying.

Usage:
    python scripts/e2e_send.py
    python scripts/e2e_send.py --to you@example.com
    python scripts/e2e_send.py --to you@example.com --company "Acme" --city "Miami"
"""
import argparse

from agent.src.config import settings  # noqa: F401 — loads .env

from agent.src.clients.supabase_client import supabase
from agent.src.functions.draft import draft
from agent.src.functions.send import send


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", default="perezalonsoenrique@gmail.com")
    parser.add_argument("--company", default="E2E Test Lead")
    parser.add_argument("--city", default="Miami")
    args = parser.parse_args()

    intel = {
        "value_prop": "Luxury residential sales across Miami-Dade.",
        "specialties": ["Luxury residential", "Waterfront properties"],
        "markets_served": ["Miami-Dade"],
        "general_email": args.to,
        "agent_count": 8,
    }

    insert = (
        supabase.table("leads")
        .insert(
            {
                "company": args.company,
                "city": args.city,
                "website": "https://example.com",
                "email": args.to,
                "status": "enriched",
                "intel_json": intel,
                "google_rating": 4.8,
                "google_reviews": 120,
            }
        )
        .execute()
    )
    lead_id = insert.data[0]["id"]
    print(f"Created lead: {lead_id}  ({args.company!r} → {args.to})")

    draft_result = draft(lead_id)
    print(
        f"Drafted: subject={draft_result.subject!r} "
        f"hook_tier={draft_result.hook_tier_used}"
    )

    pending = (
        supabase.table("messages")
        .select("id")
        .eq("lead_id", lead_id)
        .eq("direction", "outbound")
        .is_("sent_at", "null")
        .limit(1)
        .execute()
    )
    if not pending.data:
        raise SystemExit(f"No pending draft found for lead {lead_id}")
    message_id = pending.data[0]["id"]

    result = send(message_id)
    print(
        f"Sent: provider_msg_id={result['message_id']} "
        f"thread_id={result['thread_id']}"
    )
    print()
    print(f"Check {args.to} for subject: {draft_result.subject!r}")
    print("Reply to it (any short message), then run:")
    print(f"  python scripts/e2e_check.py --lead-id {lead_id}")


if __name__ == "__main__":
    main()
