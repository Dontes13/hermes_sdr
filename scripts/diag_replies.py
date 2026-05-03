"""One-off diagnostic: why aren't replies landing?

Prints:
  1. agentmail_sync cursor + inbox_id
  2. outbound msg threads in DB
  3. inbound msg rows in DB
  4. what AgentMail actually returns for the last 7d (both with and
     without the 'received' label, both with and without `after`)
"""
from datetime import datetime, timedelta, timezone

from agent.src.clients.agentmail import agentmail_client
from agent.src.clients.supabase_client import supabase


def main() -> None:
    print("=" * 60)
    print("1. agentmail_sync state")
    print("=" * 60)
    sync = (
        supabase.table("agentmail_sync").select("*").eq("id", 1).single().execute()
    )
    print(sync.data)

    print()
    print("=" * 60)
    print("2. Outbound messages (sent, with thread IDs)")
    print("=" * 60)
    outbound = (
        supabase.table("messages")
        .select("id, lead_id, subject, provider_thread_id, provider_msg_id, sent_at")
        .eq("direction", "outbound")
        .not_.is_("sent_at", "null")
        .order("sent_at", desc=True)
        .limit(20)
        .execute()
    )
    for m in outbound.data:
        print(
            f"  sent_at={m['sent_at']}  thread={m['provider_thread_id']}  "
            f"msg={m['provider_msg_id']}  subject={m['subject']!r}"
        )
    print(f"  total: {len(outbound.data)}")

    print()
    print("=" * 60)
    print("3. Inbound messages already stored")
    print("=" * 60)
    inbound = (
        supabase.table("messages")
        .select("id, lead_id, subject, provider_thread_id, provider_msg_id, sent_at, created_at")
        .eq("direction", "inbound")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    for m in inbound.data:
        print(
            f"  created={m['created_at']}  thread={m['provider_thread_id']}  "
            f"subject={m['subject']!r}"
        )
    print(f"  total stored: {len(inbound.data)}")

    print()
    print("=" * 60)
    print("4a. AgentMail .list with labels=['received'], after=7d ago")
    print("=" * 60)
    inbox_id = agentmail_client.get_or_create_inbox()
    print(f"  inbox_id: {inbox_id}")
    since = datetime.now(timezone.utc) - timedelta(days=7)
    sdk = agentmail_client._client
    resp = sdk.inboxes.messages.list(
        inbox_id=inbox_id,
        after=since,
        labels=["received"],
    )
    print(f"  count: {len(resp.messages)}")
    for stub in resp.messages:
        print(
            f"    ts={stub.timestamp}  labels={stub.labels}  "
            f"thread={stub.thread_id}  from={stub.from_}  subject={stub.subject!r}"
        )

    print()
    print("=" * 60)
    print("4b. AgentMail .list with NO labels filter, after=7d ago")
    print("=" * 60)
    resp2 = sdk.inboxes.messages.list(inbox_id=inbox_id, after=since)
    print(f"  count: {len(resp2.messages)}")
    for stub in resp2.messages:
        print(
            f"    ts={stub.timestamp}  labels={stub.labels}  "
            f"thread={stub.thread_id}  from={stub.from_}  subject={stub.subject!r}"
        )


if __name__ == "__main__":
    main()
