"""Recover an orphaned AgentMail thread into the DB.

Fetches messages on a given thread from AgentMail and rebuilds a
minimal lead + outbound message row so poll_replies can match future
inbound on that thread. Also rewinds the poll cursor.

Usage:
    python scripts/recover_thread.py --thread-id <uuid>
    python scripts/recover_thread.py --thread-id <uuid> --company "Acme" --city "Miami"
"""
import argparse
from datetime import datetime

from agent.src.config import settings  # noqa: F401 — loads .env

from agent.src.clients.agentmail import agentmail_client
from agent.src.clients.supabase_client import supabase


def _extract_email(raw: str) -> str:
    if "<" in raw and ">" in raw:
        return raw.split("<", 1)[1].rsplit(">", 1)[0].strip()
    return raw.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover an orphaned AgentMail thread")
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--company", default=None)
    parser.add_argument("--city", default="(unknown)")
    args = parser.parse_args()

    inbox_id = agentmail_client.get_or_create_inbox()
    sdk = agentmail_client._client

    resp = sdk.inboxes.messages.list(inbox_id=inbox_id, limit=200)
    thread_msgs = [m for m in resp.messages if m.thread_id == args.thread_id]
    if not thread_msgs:
        raise SystemExit(f"No messages found on thread {args.thread_id}")

    outbound_stubs = [m for m in thread_msgs if "sent" in (m.labels or [])]
    inbound_stubs = [m for m in thread_msgs if "received" in (m.labels or [])]
    if not outbound_stubs:
        raise SystemExit(f"No sent message found on thread {args.thread_id}")

    outbound_stubs.sort(key=lambda m: m.timestamp)
    root = outbound_stubs[0]
    full = sdk.inboxes.messages.get(inbox_id=inbox_id, message_id=root.message_id)

    if not full.to:
        raise SystemExit("Outbound has no recipient")
    email = _extract_email(full.to[0])
    company = args.company or (full.subject or f"Recovered thread {args.thread_id[:8]}")

    existing = supabase.table("leads").select("id, status").eq("email", email).execute()
    if existing.data:
        lead_id = existing.data[0]["id"]
        print(f"Found existing lead: {lead_id} ({email})")
    else:
        insert = supabase.table("leads").insert(
            {
                "company": company,
                "city": args.city,
                "email": email,
                "status": "sent",
            }
        ).execute()
        lead_id = insert.data[0]["id"]
        print(f"Created lead: {lead_id} ({email}, {company})")

    dup_out = (
        supabase.table("messages")
        .select("id")
        .eq("provider_msg_id", root.message_id)
        .execute()
    )
    if dup_out.data:
        print(f"Outbound already recorded: {dup_out.data[0]['id']}")
    else:
        sent_at_iso = (
            root.timestamp.isoformat() if isinstance(root.timestamp, datetime) else None
        )
        msg_insert = supabase.table("messages").insert(
            {
                "lead_id": lead_id,
                "direction": "outbound",
                "subject": full.subject or "",
                "body": full.text or "",
                "provider_msg_id": root.message_id,
                "provider_thread_id": args.thread_id,
                "sent_at": sent_at_iso,
            }
        ).execute()
        print(f"Created outbound row: {msg_insert.data[0]['id']} (sent_at={sent_at_iso})")

    supabase.table("agentmail_sync").update({"last_polled_at": None}).eq(
        "id", 1
    ).execute()
    print("Rewound agentmail_sync.last_polled_at → NULL")

    print()
    print(f"Thread {args.thread_id} stitched. Pending inbound items:")
    for m in inbound_stubs:
        print(f"  {m.message_id} @ {m.timestamp}  from={m.from_}")
    print()
    print("Next step: run `make poll-replies` to pull the replies into the DB.")


if __name__ == "__main__":
    main()
