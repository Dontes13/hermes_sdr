"""LinkedIn send path — dispatched from send() based on message.channel.

Sends via Unipile and updates the lead's linkedin_state to reflect the
new state of the relationship:

  channel='linkedin_invite' → linkedin_state='invite_sent'
  channel='linkedin_dm'     → linkedin_state stays 'connected' (DM doesn't
                              transition the connection itself)

Daily caps are enforced at the campaign-runner / scheduler layer, not here
— this function is the lowest layer and is also reachable directly from
the manual API path. Same pattern as send().
"""

from datetime import datetime, timezone

import structlog

from agent.src.clients.supabase_client import supabase
from agent.src.clients.unipile import unipile_client
from agent.src.exceptions import SendError, UnipileError

log = structlog.get_logger(__name__)


def send_linkedin(message_id: str) -> dict:
    """Send a LinkedIn invite or DM via Unipile.

    Returns {'message_id': str, 'chat_id'|'invite_id': str}.
    """
    msg_resp = (
        supabase.table("messages")
        .select("*")
        .eq("id", message_id)
        .single()
        .execute()
    )
    msg = msg_resp.data

    if msg["direction"] != "outbound":
        raise SendError(f"Message {message_id} is not outbound")
    if msg["sent_at"] is not None:
        raise SendError(f"Message {message_id} already sent at {msg['sent_at']}")
    if msg["channel"] not in ("linkedin_invite", "linkedin_dm"):
        raise SendError(
            f"send_linkedin called with channel={msg['channel']!r}; "
            f"expected linkedin_invite or linkedin_dm"
        )

    lead_resp = (
        supabase.table("leads")
        .select("*")
        .eq("id", msg["lead_id"])
        .single()
        .execute()
    )
    lead = lead_resp.data

    if not lead.get("linkedin_url"):
        raise SendError(
            f"Lead {lead['id']} ({lead['company']}) has no linkedin_url"
        )
    if lead.get("status") == "unsubscribed":
        raise SendError(f"Lead {lead['id']} is unsubscribed")

    try:
        if msg["channel"] == "linkedin_invite":
            if lead.get("linkedin_state") is not None:
                raise SendError(
                    f"Lead {lead['id']} already has linkedin_state="
                    f"{lead['linkedin_state']!r}; refusing to re-invite"
                )
            result = unipile_client.send_invite(
                linkedin_url=lead["linkedin_url"],
                note=msg["body"],
            )
            provider_msg_id = result.get("invite_id", "")
            provider_thread_id = None
        else:  # linkedin_dm
            if lead.get("linkedin_state") != "connected":
                raise SendError(
                    f"Lead {lead['id']} linkedin_state="
                    f"{lead.get('linkedin_state')!r}; DM requires 'connected'"
                )
            # Reuse the chat_id from any prior DM on this lead so the
            # conversation threads correctly. None → start a new chat.
            prior = (
                supabase.table("messages")
                .select("provider_thread_id")
                .eq("lead_id", lead["id"])
                .eq("channel", "linkedin_dm")
                .not_.is_("provider_thread_id", "null")
                .limit(1)
                .execute()
            )
            chat_id = prior.data[0]["provider_thread_id"] if prior.data else None
            result = unipile_client.send_message(
                body=msg["body"],
                chat_id=chat_id,
                linkedin_url=lead["linkedin_url"] if not chat_id else None,
            )
            provider_msg_id = result.get("message_id", "")
            provider_thread_id = result.get("chat_id") or chat_id
    except UnipileError as e:
        log.error(
            "send_linkedin_failed",
            message_id=message_id,
            lead_id=lead["id"],
            channel=msg["channel"],
            error=str(e),
        )
        raise SendError(f"unipile send failed: {e}") from e

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("messages").update(
        {
            "provider_msg_id": provider_msg_id,
            "provider_thread_id": provider_thread_id,
            "sent_at": now,
        }
    ).eq("id", message_id).execute()

    # Lead state transitions: invite → invite_sent. DM doesn't change state.
    if msg["channel"] == "linkedin_invite":
        supabase.table("leads").update({"linkedin_state": "invite_sent"}).eq(
            "id", lead["id"]
        ).execute()

    log.info(
        "send_linkedin_success",
        lead_id=lead["id"],
        company=lead["company"],
        channel=msg["channel"],
        provider_msg_id=provider_msg_id,
    )
    return result
