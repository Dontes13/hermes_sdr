import re
from pathlib import Path
from typing import Literal

import structlog
from jinja2 import Template
from pydantic import BaseModel

from agent.src.clients.gemini import gemini
from agent.src.clients.supabase_client import supabase
from agent.src.exceptions import ReplyDraftError
from agent.src.functions.knowledge_base import load_knowledge_base

log = structlog.get_logger(__name__)

REPLY_TEMPLATE = Template(
    (Path(__file__).parent.parent / "prompts" / "reply.j2").read_text()
)

_RE_PREFIX = re.compile(r"^(re:\s*)+", re.IGNORECASE)


class ReplyDraftResult(BaseModel):
    body: str
    intent: Literal[
        "interested", "question", "objection", "booking", "negative", "other"
    ]


def draft_reply(inbound_message_id: str) -> ReplyDraftResult:
    """Generate an AI reply draft for an inbound message.

    Stores the draft as a pending outbound message threaded onto the same
    provider_thread_id. Does NOT send. Raises ReplyDraftError on failure.
    """
    # 1. Load inbound message
    try:
        inbound_resp = (
            supabase.table("messages")
            .select("*")
            .eq("id", inbound_message_id)
            .single()
            .execute()
        )
    except Exception as e:
        raise ReplyDraftError(f"inbound message {inbound_message_id} not found: {e}") from e
    inbound = inbound_resp.data
    if inbound["direction"] != "inbound":
        raise ReplyDraftError(
            f"message {inbound_message_id} is direction={inbound['direction']}, expected inbound"
        )

    # 2. Load lead
    lead_resp = (
        supabase.table("leads")
        .select("*")
        .eq("id", inbound["lead_id"])
        .single()
        .execute()
    )
    lead = lead_resp.data

    # 3. Load full thread history (all messages for this lead, chronological)
    thread_resp = (
        supabase.table("messages")
        .select("direction, subject, body, sent_at, created_at")
        .eq("lead_id", lead["id"])
        .order("created_at", desc=False)
        .execute()
    )
    thread = thread_resp.data

    # 4. Load config (sender info + calendly)
    config_resp = (
        supabase.table("config")
        .select("key, value")
        .in_("key", ["sender_name", "sender_title", "calendly_link"])
        .execute()
    )
    config_map = {row["key"]: row["value"] for row in config_resp.data}
    sender_name = config_map.get("sender_name", "Enrique")
    sender_title = config_map.get("sender_title", "CTO, Helios Marketing")
    calendly_link = config_map.get("calendly_link", "")

    # 5. Render prompt
    intel = lead.get("intel_json") or {}
    prompt = REPLY_TEMPLATE.render(
        sender_name=sender_name,
        sender_title=sender_title,
        company=lead["company"],
        city=lead["city"],
        lead=lead,
        intel=intel,
        calendly_link=calendly_link,
        thread=thread,
        inbound=inbound,
        knowledge_base=load_knowledge_base(),
    )

    # 6. Call Gemini Pro
    try:
        result = gemini.generate_json_pro(prompt, ReplyDraftResult)
    except Exception as e:
        raise ReplyDraftError(f"gemini reply draft failed: {e}") from e

    # 7. Delete any existing pending reply draft on this thread (scoped to avoid
    # wiping unrelated cold drafts on the same lead).
    thread_id = inbound.get("provider_thread_id")
    if thread_id:
        (
            supabase.table("messages")
            .delete()
            .eq("lead_id", lead["id"])
            .eq("direction", "outbound")
            .eq("provider_thread_id", thread_id)
            .is_("sent_at", "null")
            .execute()
        )

    # 8. Build subject: strip nested "Re:" prefixes then add one fresh "Re: "
    inbound_subject = inbound.get("subject") or ""
    stripped = _RE_PREFIX.sub("", inbound_subject).strip()
    new_subject = f"Re: {stripped}" if stripped else "Re:"

    # Inherit is_test from the inbound so test-thread reply drafts stay
    # isolated from real outreach metrics.
    is_test_thread = bool(inbound.get("is_test"))

    # Inherit channel + provider from the inbound so a LinkedIn DM reply
    # is sent back through Unipile, not AgentMail. Defaults preserve the
    # historical email behavior on rows that pre-date the channel column.
    channel = inbound.get("channel") or "email"
    provider = inbound.get("provider") or (
        "unipile" if channel.startswith("linkedin") else "agentmail"
    )

    insert_resp = (
        supabase.table("messages")
        .insert(
            {
                "lead_id": lead["id"],
                "direction": "outbound",
                "channel": channel,
                "provider": provider,
                # LinkedIn DMs have no subject; suppress the synthetic Re:
                "subject": new_subject if channel == "email" else None,
                "body": result.body,
                "hook_tier_used": None,
                "hook_text": None,
                "hook_rationale": f"reply_intent={result.intent}",
                "provider_thread_id": thread_id,
                "sent_at": None,
                "is_test": is_test_thread,
            }
        )
        .execute()
    )
    new_msg_id = insert_resp.data[0]["id"]

    # 9. Log
    log.info(
        "reply_draft_created",
        lead_id=lead["id"],
        company=lead["company"],
        intent=result.intent,
        message_id=new_msg_id,
    )

    return result
