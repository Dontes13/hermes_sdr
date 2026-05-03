from datetime import datetime, timedelta, timezone

import structlog

from agent.src.clients.agentmail import agentmail_client
from agent.src.clients.supabase_client import supabase
from agent.src.functions.unsubscribe import detect_unsubscribe, handle_unsubscribe

log = structlog.get_logger(__name__)


def poll_replies() -> dict:
    """Poll AgentMail for new inbound messages since the last poll.

    Matches to leads via provider_thread_id, stores inbound rows, detects
    and handles unsubscribes, flips lead status to 'replied' for non-unsub
    replies. Idempotent: re-running skips messages already in the DB
    (dedup by provider_msg_id).

    Returns summary dict: {checked, matched, unsubscribed, new_replies}.
    """
    # 1. Read cursor from agentmail_sync; default to 7 days ago
    sync_resp = (
        supabase.table("agentmail_sync")
        .select("last_polled_at")
        .eq("id", 1)
        .single()
        .execute()
    )

    last_polled: datetime
    if sync_resp.data and sync_resp.data.get("last_polled_at"):
        last_polled = datetime.fromisoformat(sync_resp.data["last_polled_at"])
    else:
        last_polled = datetime.now(timezone.utc) - timedelta(days=7)

    # 2. Fetch inbound messages (full bodies — client does list+get internally)
    inbound = agentmail_client.list_inbound_since(last_polled)
    log.info("poll_fetched", count=len(inbound), since=last_polled.isoformat())

    summary = {
        "checked": len(inbound),
        "matched": 0,
        "unsubscribed": 0,
        "new_replies": 0,
    }

    if not inbound:
        _update_sync_cursor()
        log.info("poll_complete", **summary)
        return summary

    stored_timestamps: list[datetime] = []

    # 3. Build known thread IDs (our conversations) + mark which are test-only
    threads_resp = (
        supabase.table("messages")
        .select("provider_thread_id, is_test")
        .not_.is_("provider_thread_id", "null")
        .execute()
    )
    known_threads: set[str] = set()
    test_threads: set[str] = set()  # threads with at least one test outbound
    real_threads: set[str] = set()  # threads with at least one non-test outbound
    for r in threads_resp.data:
        tid = r.get("provider_thread_id")
        if not tid:
            continue
        known_threads.add(tid)
        if r.get("is_test"):
            test_threads.add(tid)
        else:
            real_threads.add(tid)
    # A thread is treated as test only if it has NO real outbound in it.
    test_only_threads = test_threads - real_threads

    # 4. Build processed message IDs (dedup guard)
    processed_resp = (
        supabase.table("messages")
        .select("provider_msg_id")
        .eq("direction", "inbound")
        .not_.is_("provider_msg_id", "null")
        .execute()
    )
    processed_ids = {
        r["provider_msg_id"]
        for r in processed_resp.data
        if r.get("provider_msg_id")
    }

    for m in inbound:
        if m["thread_id"] not in known_threads:
            continue
        if m["message_id"] in processed_ids:
            continue

        # Look up lead via thread_id (join through outbound message row)
        lead_lookup = (
            supabase.table("messages")
            .select("lead_id")
            .eq("provider_thread_id", m["thread_id"])
            .eq("direction", "outbound")
            .limit(1)
            .execute()
        )
        if not lead_lookup.data:
            continue
        lead_id = lead_lookup.data[0]["lead_id"]

        # Serialize timestamp
        sent_at_iso = None
        ts = m.get("timestamp")
        if ts is not None:
            if isinstance(ts, datetime):
                sent_at_iso = ts.isoformat()
            else:
                sent_at_iso = str(ts)

        # Inbound on a test-only thread inherits is_test. Real threads stay
        # untagged so existing reply flow is unchanged.
        is_test_inbound = m["thread_id"] in test_only_threads

        # Insert inbound row
        supabase.table("messages").insert(
            {
                "lead_id": lead_id,
                "direction": "inbound",
                "subject": m.get("subject", ""),
                "body": m.get("text", ""),
                "provider_msg_id": m["message_id"],
                "provider_thread_id": m["thread_id"],
                "sent_at": sent_at_iso,
                "is_test": is_test_inbound,
            }
        ).execute()
        summary["matched"] += 1
        if isinstance(ts, datetime):
            stored_timestamps.append(ts)

        # Unsubscribe detection — use extracted_text (new reply content
        # only) when available. Gmail replies include the full quoted
        # thread history, and our own compliance footer ("...reply
        # 'unsubscribe'...") would false-trigger the regex on every reply.
        unsub_body = m.get("extracted_text") or m.get("text", "")
        if detect_unsubscribe(unsub_body):
            handle_unsubscribe(lead_id, m["message_id"])
            summary["unsubscribed"] += 1
            continue

        # Auto-draft a reply via Gemini and store as pending outbound message.
        # Inline import keeps the dependency direction clean. Failures here
        # must never crash the batch — the lead still flips to 'replied' and
        # the user can regenerate via /api/replies/{id}/regenerate.
        try:
            from agent.src.functions.draft_reply import draft_reply

            new_inbound = (
                supabase.table("messages")
                .select("id")
                .eq("provider_msg_id", m["message_id"])
                .eq("direction", "inbound")
                .single()
                .execute()
            )
            if new_inbound.data:
                draft_reply(new_inbound.data["id"])
        except Exception as e:
            log.error(
                "auto_draft_reply_failed",
                lead_id=lead_id,
                inbound_provider_msg_id=m["message_id"],
                error=str(e),
            )

        # Flip to 'replied' unless terminal state — but NOT for test threads,
        # since those were never "real" sends and the lead should stay at
        # whatever it was (usually 'drafted') so the user can still Approve
        # for a genuine outreach later.
        if not is_test_inbound:
            lead_state = (
                supabase.table("leads")
                .select("status")
                .eq("id", lead_id)
                .single()
                .execute()
            )
            if lead_state.data and lead_state.data["status"] not in (
                "booked",
                "unsubscribed",
            ):
                supabase.table("leads").update({"status": "replied"}).eq(
                    "id", lead_id
                ).execute()
        summary["new_replies"] += 1

        # Avoid re-processing within this same poll if duplicates appear
        processed_ids.add(m["message_id"])

    # Cursor policy: advance to the newest stored message if we stored any.
    # If we saw messages but matched none, HOLD the cursor — this lets the
    # poll catch up on previously-skipped items once the DB re-accumulates
    # outbound threads (e.g., after a reset_db run). Advancing blindly to
    # now() would strand the unmatched messages behind the cursor.
    if stored_timestamps:
        _update_sync_cursor(max(stored_timestamps) + timedelta(microseconds=1))
    else:
        log.warning(
            "poll_cursor_held",
            reason="batch had items but none stored; retrying on next poll",
            batch_size=len(inbound),
        )
    log.info("poll_complete", **summary)
    return summary


def _update_sync_cursor(new_cursor: datetime | None = None) -> None:
    cursor = new_cursor or datetime.now(timezone.utc)
    supabase.table("agentmail_sync").update(
        {"last_polled_at": cursor.isoformat()}
    ).eq("id", 1).execute()
