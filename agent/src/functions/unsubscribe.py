import re
from datetime import datetime, timezone

import structlog

from agent.src.clients.agentmail import agentmail_client
from agent.src.clients.gemini import gemini
from agent.src.clients.supabase_client import supabase

log = structlog.get_logger(__name__)

UNSUB_PATTERNS = [
    r"\bunsubscribe\b",
    r"\bremove me\b",
    r"\btake me off\b",
    r"\bstop emailing\b",
    r"\bdo not (contact|email|message)\b",
    r"\bnot interested\b",
    r"\bplease stop\b",
    r"\bopt[- ]?out\b",
    r"\bwe're all set\b",
    r"\bwrong person\b",
]

_UNSUB_RE = re.compile("|".join(UNSUB_PATTERNS), re.IGNORECASE)


def detect_unsubscribe(body: str) -> bool:
    """Returns True if the body contains an unsubscribe intent.

    Step 1: regex fast path. If any pattern matches, return True.
    Step 2: Gemini Flash fallback for non-matches.
    """
    if _UNSUB_RE.search(body):
        log.info("unsub_detected", source="regex")
        return True

    prompt = (
        "Did this email ask to stop receiving further emails, "
        "opt out, or otherwise indicate they don't want further contact? "
        "Reply with only 'true' or 'false'.\n\n"
        f"Email body:\n{body}"
    )
    response = gemini.generate_text_flash(prompt)
    is_unsub = "true" in response.lower()
    log.info("unsub_detected", source="llm", result=is_unsub)
    return is_unsub


def handle_unsubscribe(lead_id: str, inbound_provider_msg_id: str) -> None:
    """Handle a detected unsubscribe.

    Updates lead status to 'unsubscribed', sends a threaded ack via
    AgentMail's reply() endpoint, stores the ack as an outbound message row.
    The inbound_provider_msg_id is AgentMail's message id (not our DB row id).
    """
    # 1. Update lead status
    supabase.table("leads").update({"status": "unsubscribed"}).eq(
        "id", lead_id
    ).execute()

    # 2. Send threaded ack
    ack_text = (
        "You got it \u2014 I've removed you from my list. "
        "Apologies for the intrusion.\n\n\u2014 Enrique"
    )
    result = agentmail_client.reply_to_message(
        reply_to_message_id=inbound_provider_msg_id,
        text=ack_text,
    )

    # 3. Store ack as outbound message row
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("messages").insert(
        {
            "lead_id": lead_id,
            "direction": "outbound",
            "subject": "Re: unsubscribe",
            "body": ack_text,
            "provider_msg_id": result["message_id"],
            "provider_thread_id": result["thread_id"],
            "sent_at": now,
        }
    ).execute()

    lead_resp = (
        supabase.table("leads")
        .select("company")
        .eq("id", lead_id)
        .single()
        .execute()
    )
    log.info(
        "unsubscribe_handled",
        lead_id=lead_id,
        company=lead_resp.data["company"],
    )
