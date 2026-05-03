"""E2E test step 2: poll AgentMail and dump the thread for a test lead.

Runs poll_replies() to pull inbound messages, then prints the full
message trail for the given lead — including any auto-generated
pending reply draft from Gemini. Exit code is 0 if a reply landed
and an AI reply draft was produced.

Usage:
    python scripts/e2e_check.py                       # polls, shows 5 most recent
    python scripts/e2e_check.py --lead-id <uuid>      # focus one lead
"""
import argparse
import sys

from agent.src.config import settings  # noqa: F401

from agent.src.clients.supabase_client import supabase
from agent.src.functions.poll import poll_replies


def _print_lead(lead_id: str) -> tuple[bool, bool]:
    lead = (
        supabase.table("leads").select("*").eq("id", lead_id).single().execute().data
    )
    print(f"=== Lead {lead_id} ===")
    print(
        f"  company={lead['company']!r}  email={lead['email']}  status={lead['status']}"
    )

    msgs = (
        supabase.table("messages")
        .select("direction, subject, body, sent_at, created_at")
        .eq("lead_id", lead_id)
        .order("created_at")
        .execute()
    )
    has_inbound = False
    has_pending_reply = False
    for m in msgs.data:
        state = "SENT" if m["sent_at"] else "PENDING"
        print(f"  [{m['direction']:8} {state:7}] {m['subject']!r}")
        body = (m["body"] or "").strip()
        preview = body[:220].replace("\n", " / ")
        suffix = "..." if len(body) > 220 else ""
        print(f"      {preview}{suffix}")
        if m["direction"] == "inbound":
            has_inbound = True
        if m["direction"] == "outbound" and m["sent_at"] is None:
            has_pending_reply = True
    print()
    return has_inbound, has_pending_reply


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lead-id", default=None)
    args = parser.parse_args()

    print("Polling AgentMail for inbound replies...")
    summary = poll_replies()
    print(f"Poll summary: {summary}")
    print()

    if args.lead_id:
        lead_ids = [args.lead_id]
    else:
        recent = (
            supabase.table("leads")
            .select("id")
            .in_("status", ["sent", "replied", "booked", "unsubscribed"])
            .order("updated_at", desc=True)
            .limit(5)
            .execute()
        )
        lead_ids = [row["id"] for row in recent.data]
        if not lead_ids:
            print("No sent/replied leads found. Run scripts/e2e_send.py first.")
            return

    any_inbound = False
    any_pending_reply = False
    for lid in lead_ids:
        inbound, pending = _print_lead(lid)
        any_inbound = any_inbound or inbound
        any_pending_reply = any_pending_reply or pending

    if args.lead_id:
        if not any_inbound:
            print("No reply received yet. Reply to the email and re-run this script.")
            sys.exit(2)
        if not any_pending_reply:
            print("Reply landed but no AI draft was created (check logs).")
            sys.exit(3)
        print("E2E success: reply landed and AI draft is pending approval.")


if __name__ == "__main__":
    main()
