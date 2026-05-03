from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.src.api.deps import CurrentUser
from agent.src.clients.agentmail import agentmail_client
from agent.src.clients.supabase_client import supabase
from agent.src.functions.send import COMPLIANCE_FOOTER

log = structlog.get_logger(__name__)

router = APIRouter()


class TestSendBody(BaseModel):
    lead_id: str
    to: str


@router.post("")
def test_send(_user: CurrentUser, body: TestSendBody):
    """Send a draft to a test email address.

    The test send is recorded as a `messages` row with `is_test=true` so
    the reply poller can match inbound back to the thread and surface it
    in /replies. The source draft stays pending and the lead's status is
    NOT changed — you can still Approve the real lead later for a genuine
    outreach. Stats queries exclude `is_test=true` rows, so the funnel
    isn't polluted.
    """
    # Find the pending outbound draft
    drafts = (
        supabase.table("messages")
        .select("*")
        .eq("lead_id", body.lead_id)
        .eq("direction", "outbound")
        .is_("sent_at", "null")
        .execute()
    )

    if not drafts.data:
        raise HTTPException(400, "No pending draft found for this lead")

    message = drafts.data[0]
    full_body = message["body"] + COMPLIANCE_FOOTER

    # Send to the test address (NOT the lead's real email)
    result = agentmail_client.send_message(
        to=body.to,
        subject=message["subject"],
        text=full_body,
    )

    # Record a test message row so replies can be matched + surfaced.
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("messages").insert(
        {
            "lead_id": body.lead_id,
            "direction": "outbound",
            "subject": message["subject"],
            "body": message["body"],
            "hook_tier_used": message.get("hook_tier_used"),
            "hook_text": message.get("hook_text"),
            "hook_rationale": message.get("hook_rationale"),
            "provider_msg_id": result["message_id"],
            "provider_thread_id": result["thread_id"],
            "sent_at": now,
            "is_test": True,
        }
    ).execute()

    log.info(
        "test_send_recorded",
        lead_id=body.lead_id,
        to=body.to,
        provider_msg_id=result["message_id"],
        thread_id=result["thread_id"],
    )

    return {
        "sent": True,
        "to": body.to,
        "subject": message["subject"],
        "provider_thread_id": result["thread_id"],
    }
