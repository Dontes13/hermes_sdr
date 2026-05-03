from datetime import datetime, timedelta, timezone

import structlog

from agent.src.clients.agentmail import agentmail_client
from agent.src.clients.supabase_client import supabase
from agent.src.config import settings
from agent.src.exceptions import AgentMailError, SendError

log = structlog.get_logger(__name__)

COMPLIANCE_FOOTER = """

—
Enrique, Helios Marketing
If you'd rather not hear from me, just reply "unsubscribe" and I'll remove you immediately."""


def send(message_id: str) -> dict:
    """Send a drafted outbound message via AgentMail.

    Returns {'message_id': str, 'thread_id': str} on success.
    Raises SendError on validation failures, double-send attempts, or
    provider errors.
    """
    # 1. Load message row
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

    # 1a. Channel dispatch — LinkedIn messages route to Unipile. Inline
    # import keeps the dependency graph clean (send_linkedin imports from
    # this module's neighbors but not from send itself).
    if msg.get("channel") and msg["channel"] != "email":
        from agent.src.functions.send_linkedin import send_linkedin

        return send_linkedin(message_id)

    # 2. Load the associated lead
    lead_resp = (
        supabase.table("leads")
        .select("*")
        .eq("id", msg["lead_id"])
        .single()
        .execute()
    )
    lead = lead_resp.data

    if not lead.get("email"):
        raise SendError(
            f"Lead {lead['id']} ({lead['company']}) has no email address"
        )

    # 3. Detect reply vs fresh: reply drafts are pre-populated with
    # provider_thread_id at draft time (by draft_reply); fresh cold drafts are not.
    is_reply = bool(msg.get("provider_thread_id"))

    # 4. Status check depends on send type
    if is_reply:
        if lead["status"] not in ("replied", "booked"):
            raise SendError(
                f"Lead {lead['id']} has status '{lead['status']}', "
                f"reply send expected 'replied' or 'booked'"
            )
    else:
        if lead["status"] not in ("drafted", "approved"):
            raise SendError(
                f"Lead {lead['id']} has status '{lead['status']}', "
                f"expected 'drafted' or 'approved'"
            )

    # 5. Build full body + send. Compliance footer only on fresh cold sends.
    try:
        if is_reply:
            full_body = msg["body"]
            # Find the latest inbound message on this thread to reply to
            inbound_resp = (
                supabase.table("messages")
                .select("provider_msg_id")
                .eq("provider_thread_id", msg["provider_thread_id"])
                .eq("direction", "inbound")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if not inbound_resp.data:
                raise SendError(
                    f"reply send: no inbound message found for thread "
                    f"{msg['provider_thread_id']}"
                )
            result = agentmail_client.reply_to_message(
                reply_to_message_id=inbound_resp.data[0]["provider_msg_id"],
                text=full_body,
            )
        else:
            full_body = msg["body"] + COMPLIANCE_FOOTER
            result = agentmail_client.send_message(
                to=lead["email"],
                subject=msg["subject"],
                text=full_body,
            )
    except AgentMailError as e:
        log.error(
            "send_failed",
            message_id=message_id,
            lead_id=lead["id"],
            error=str(e),
        )
        raise SendError(f"agentmail send failed: {e}") from e

    # 6. Update message row
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("messages").update(
        {
            "provider_msg_id": result["message_id"],
            "provider_thread_id": result["thread_id"],
            "sent_at": now,
        }
    ).eq("id", message_id).execute()

    # 7. Update lead status — only on fresh sends. Replies leave the lead
    # at 'replied' or 'booked' (don't regress the sales funnel).
    #
    # Also stamp linkedin_followup_eligible_at iff the lead has a LinkedIn
    # URL and hasn't already been touched on LinkedIn — this is what the
    # cadence ticker scans for. Skip for replies (the lead is past the
    # silence-window logic).
    if not is_reply:
        lead_update: dict = {"status": "sent"}
        if lead.get("linkedin_url") and lead.get("linkedin_state") is None:
            eligible_at = datetime.now(timezone.utc) + timedelta(
                days=settings.LINKEDIN_FOLLOWUP_DAYS
            )
            lead_update["linkedin_followup_eligible_at"] = eligible_at.isoformat()
        supabase.table("leads").update(lead_update).eq("id", lead["id"]).execute()

    # 8. Log success
    log.info(
        "send_success",
        lead_id=lead["id"],
        company=lead["company"],
        recipient=lead["email"],
        message_id=message_id,
        provider_msg_id=result["message_id"],
    )

    return result
