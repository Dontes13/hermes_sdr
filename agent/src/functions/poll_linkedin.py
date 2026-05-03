"""Poll Unipile for LinkedIn invite-status updates and inbound DMs.

Two pulls per call:

  1. Invite-status: any pending invite that is now 'accepted' flips the
     lead to linkedin_state='connected' (and the next campaign tick
     drafts the DM). 'declined' flips to 'declined'.

  2. Inbound DMs: matched to a lead via provider_thread_id (chat id) on
     prior outbound LinkedIn messages, or by sender_url == leads.linkedin_url
     as fallback. Inserted as messages rows; auto-drafts a reply via the
     same draft_reply machinery as email replies.

Cursors live in unipile_sync (one timestamp per stream). Same hold-on-no-match
policy as poll_replies(): if the API returned items but none matched our
DB, hold the cursor — better to re-poll than strand items behind it.
"""

from datetime import datetime, timedelta, timezone

import structlog

from agent.src.clients.supabase_client import supabase
from agent.src.clients.unipile import unipile_client
from agent.src.functions.unsubscribe import detect_unsubscribe, handle_unsubscribe

log = structlog.get_logger(__name__)


def _read_cursor(field: str) -> datetime:
    resp = (
        supabase.table("unipile_sync")
        .select(field)
        .eq("id", 1)
        .single()
        .execute()
    )
    val = (resp.data or {}).get(field)
    if val:
        return datetime.fromisoformat(val)
    return datetime.now(timezone.utc) - timedelta(days=7)


def _write_cursor(field: str, dt: datetime) -> None:
    supabase.table("unipile_sync").update({field: dt.isoformat()}).eq(
        "id", 1
    ).execute()


def _normalize_url(url: str | None) -> str | None:
    """Lowercase + strip trailing slash so URL comparisons are stable."""
    if not url:
        return None
    return url.rstrip("/").lower()


def poll_linkedin() -> dict:
    """Pull invite-status updates and inbound DMs from Unipile.

    Returns summary dict.
    """
    if not unipile_client.enabled:
        log.info("poll_linkedin_skipped", reason="unipile_disabled")
        return {"skipped": "unipile_disabled"}

    summary = {
        "invite_accepted": 0,
        "invite_declined": 0,
        "dms_matched": 0,
        "unsubscribed": 0,
        "errors": 0,
    }

    # ── 1. Invite-status updates ──
    invite_cursor = _read_cursor("last_invite_polled_at")
    try:
        invite_updates = unipile_client.list_invite_status_since(invite_cursor)
    except Exception as e:
        log.warning("poll_linkedin_invite_list_failed", error=str(e))
        invite_updates = []
        summary["errors"] += 1

    if invite_updates:
        # Build provider_msg_id → lead_id map from outbound invites we sent.
        invite_ids = [it["invite_id"] for it in invite_updates if it["invite_id"]]
        if invite_ids:
            msg_resp = (
                supabase.table("messages")
                .select("lead_id, provider_msg_id")
                .eq("channel", "linkedin_invite")
                .eq("direction", "outbound")
                .in_("provider_msg_id", invite_ids)
                .execute()
            )
            lead_by_invite = {
                r["provider_msg_id"]: r["lead_id"] for r in msg_resp.data
            }
        else:
            lead_by_invite = {}

        for it in invite_updates:
            lead_id = lead_by_invite.get(it["invite_id"])
            if not lead_id:
                continue
            new_state: str | None = None
            if it["status"] == "accepted":
                new_state = "connected"
                summary["invite_accepted"] += 1
            elif it["status"] == "declined":
                new_state = "declined"
                summary["invite_declined"] += 1
            if new_state:
                supabase.table("leads").update(
                    {"linkedin_state": new_state}
                ).eq("id", lead_id).execute()

        _write_cursor("last_invite_polled_at", datetime.now(timezone.utc))

    # ── 2. Inbound DMs ──
    chat_cursor = _read_cursor("last_chat_polled_at")
    try:
        inbound = unipile_client.list_inbound_since(chat_cursor)
    except Exception as e:
        log.warning("poll_linkedin_chat_list_failed", error=str(e))
        inbound = []
        summary["errors"] += 1

    log.info(
        "poll_linkedin_inbound_fetched",
        count=len(inbound),
        since=chat_cursor.isoformat(),
    )

    if not inbound:
        _write_cursor("last_chat_polled_at", datetime.now(timezone.utc))
        log.info("poll_linkedin_complete", **summary)
        return summary

    # Dedup: skip messages already stored.
    existing_ids_resp = (
        supabase.table("messages")
        .select("provider_msg_id")
        .eq("direction", "inbound")
        .eq("channel", "linkedin_dm")
        .not_.is_("provider_msg_id", "null")
        .execute()
    )
    seen_ids = {
        r["provider_msg_id"] for r in existing_ids_resp.data if r.get("provider_msg_id")
    }

    # Lookup table: chat_id → lead_id (from any prior linkedin_dm we sent).
    chat_lookup_resp = (
        supabase.table("messages")
        .select("lead_id, provider_thread_id")
        .eq("channel", "linkedin_dm")
        .not_.is_("provider_thread_id", "null")
        .execute()
    )
    lead_by_chat = {
        r["provider_thread_id"]: r["lead_id"]
        for r in chat_lookup_resp.data
        if r.get("provider_thread_id")
    }

    # Fallback lookup: linkedin_url → lead_id, for the very first inbound
    # message on a thread (we won't have stored the chat_id yet if the
    # invite was the only outbound).
    li_url_resp = (
        supabase.table("leads")
        .select("id, linkedin_url")
        .not_.is_("linkedin_url", "null")
        .execute()
    )
    lead_by_url = {
        _normalize_url(r["linkedin_url"]): r["id"]
        for r in li_url_resp.data
        if r.get("linkedin_url")
    }

    stored_timestamps: list[datetime] = []
    for m in inbound:
        if m["message_id"] in seen_ids:
            continue
        lead_id = lead_by_chat.get(m["chat_id"]) or lead_by_url.get(
            _normalize_url(m.get("sender_url"))
        )
        if not lead_id:
            continue

        sent_at_iso = None
        ts = m.get("sent_at")
        if isinstance(ts, datetime):
            sent_at_iso = ts.isoformat()
            stored_timestamps.append(ts)
        elif isinstance(ts, str):
            sent_at_iso = ts

        supabase.table("messages").insert(
            {
                "lead_id": lead_id,
                "direction": "inbound",
                "channel": "linkedin_dm",
                "provider": "unipile",
                "subject": None,
                "body": m.get("body") or "",
                "provider_msg_id": m["message_id"],
                "provider_thread_id": m["chat_id"],
                "sent_at": sent_at_iso,
            }
        ).execute()
        summary["dms_matched"] += 1

        # Unsubscribe detection — same regex as email; LinkedIn doesn't
        # have a CAN-SPAM equivalent but we honor "stop"/"unsubscribe" as
        # an explicit no.
        if detect_unsubscribe(m.get("body") or ""):
            handle_unsubscribe(lead_id, m["message_id"])
            summary["unsubscribed"] += 1
            seen_ids.add(m["message_id"])
            continue

        # Auto-draft reply. Inline import + try/except keeps reply failures
        # from killing the polling batch (same pattern as poll.py).
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
                "poll_linkedin_auto_draft_failed",
                lead_id=lead_id,
                provider_msg_id=m["message_id"],
                error=str(e),
            )

        # Flip lead status to 'replied' (parallel to email flow) unless
        # terminal. LinkedIn replies are still a strong buy-signal — same
        # surfacing as email replies in the dashboard.
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

        seen_ids.add(m["message_id"])

    if stored_timestamps:
        _write_cursor(
            "last_chat_polled_at",
            max(stored_timestamps) + timedelta(microseconds=1),
        )
    else:
        log.warning(
            "poll_linkedin_cursor_held",
            reason="batch had items but none stored",
            batch_size=len(inbound),
        )

    log.info("poll_linkedin_complete", **summary)
    return summary
