"""LinkedIn drafting — invites and DMs.

Mirrors `draft.py` but writes a row with channel='linkedin_invite' or
'linkedin_dm' and provider='unipile'. The shared `messages` table is the
queue: anything with sent_at IS NULL is a pending draft, regardless of
channel, so the same approvals UI works for both.
"""

from pathlib import Path
from typing import Literal, Optional

import structlog
from jinja2 import Template
from pydantic import BaseModel

from agent.src.clients.gemini import gemini
from agent.src.clients.supabase_client import supabase
from agent.src.clients.unipile import INVITE_NOTE_MAX_CHARS
from agent.src.exceptions import LinkedInDraftError
from agent.src.functions.hook_tiers import TIER_NAMES, compute_available_tiers
from agent.src.functions.knowledge_base import load_knowledge_base

log = structlog.get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
INVITE_TEMPLATE = Template((_PROMPTS_DIR / "linkedin_invite.j2").read_text())
DM_TEMPLATE = Template((_PROMPTS_DIR / "linkedin_dm.j2").read_text())


class _LinkedInResult(BaseModel):
    body: str
    hook_tier_used: int
    hook_text: str
    hook_rationale: str


def _load_sender() -> tuple[str, str]:
    config_resp = (
        supabase.table("config")
        .select("key, value")
        .in_("key", ["sender_name", "sender_title"])
        .execute()
    )
    config_map = {row["key"]: row["value"] for row in config_resp.data}
    return (
        config_map.get("sender_name", "Enrique"),
        config_map.get("sender_title", "CTO, Helios Marketing"),
    )


def _load_sample_email(lead: dict) -> Optional[str]:
    if not lead.get("campaign_id"):
        return None
    camp_resp = (
        supabase.table("campaigns")
        .select("sample_email")
        .eq("id", lead["campaign_id"])
        .limit(1)
        .execute()
    )
    if not camp_resp.data:
        return None
    return camp_resp.data[0].get("sample_email")


def _replace_pending_draft(lead_id: str, channel: str) -> None:
    """Delete any existing unsent draft of this channel — the new one
    supersedes. Sent rows are preserved (sent_at IS NOT NULL filter)."""
    (
        supabase.table("messages")
        .delete()
        .eq("lead_id", lead_id)
        .eq("channel", channel)
        .eq("direction", "outbound")
        .is_("sent_at", "null")
        .execute()
    )


def draft_invite(lead_id: str) -> _LinkedInResult:
    """Generate a LinkedIn connection-invitation note for a lead.

    Requires: leads.linkedin_url IS NOT NULL and linkedin_state IS NULL
    (we haven't already invited). Inserts a messages row with
    channel='linkedin_invite', provider='unipile', sent_at=NULL.

    Raises LinkedInDraftError on validation failure or if both attempts
    exceed the 280-char LinkedIn note limit.
    """
    lead_resp = (
        supabase.table("leads").select("*").eq("id", lead_id).single().execute()
    )
    lead = lead_resp.data

    if not lead.get("linkedin_url"):
        raise LinkedInDraftError(
            f"Lead {lead_id} has no linkedin_url — run enrichment or set manually"
        )
    if lead.get("linkedin_state") is not None:
        raise LinkedInDraftError(
            f"Lead {lead_id} already has linkedin_state="
            f"{lead['linkedin_state']!r}; cannot re-invite"
        )
    if lead.get("status") == "unsubscribed":
        raise LinkedInDraftError(f"Lead {lead_id} is unsubscribed")

    sender_name, sender_title = _load_sender()
    available_tiers = compute_available_tiers(lead)
    sample_email = _load_sample_email(lead)
    intel = lead.get("intel_json") or {}

    prompt = INVITE_TEMPLATE.render(
        sender_name=sender_name,
        sender_title=sender_title,
        company=lead["company"],
        city=lead["city"],
        owner_name=lead.get("owner_name"),
        google_rating=lead.get("google_rating"),
        google_reviews=lead.get("google_reviews"),
        intel=intel,
        available_tiers=available_tiers,
        tier_descriptions=TIER_NAMES,
        sample_email=sample_email,
    )

    result = gemini.generate_json_pro(prompt, _LinkedInResult)

    # 280-char enforcement — one corrective retry, then hard fail.
    if len(result.body) > INVITE_NOTE_MAX_CHARS:
        log.warning(
            "linkedin_invite_too_long",
            lead_id=lead_id,
            length=len(result.body),
        )
        corrective = (
            prompt
            + f"\n\nCORRECTION: your previous note was {len(result.body)} "
            f"characters. The HARD ceiling is {INVITE_NOTE_MAX_CHARS}. "
            f"Rewrite — keep the hook, drop a sentence, get under the limit."
        )
        result = gemini.generate_json_pro(corrective, _LinkedInResult)
        if len(result.body) > INVITE_NOTE_MAX_CHARS:
            raise LinkedInDraftError(
                f"invite note exceeds {INVITE_NOTE_MAX_CHARS} chars after retry "
                f"(got {len(result.body)})"
            )

    if result.hook_tier_used not in available_tiers:
        log.warning(
            "linkedin_invalid_tier",
            lead_id=lead_id,
            attempted_tier=result.hook_tier_used,
            available=available_tiers,
        )

    _replace_pending_draft(lead_id, "linkedin_invite")
    supabase.table("messages").insert(
        {
            "lead_id": lead_id,
            "direction": "outbound",
            "channel": "linkedin_invite",
            "provider": "unipile",
            "subject": None,  # invites have no subject
            "body": result.body,
            "hook_tier_used": result.hook_tier_used,
            "hook_text": result.hook_text,
            "hook_rationale": result.hook_rationale,
        }
    ).execute()

    log.info(
        "linkedin_invite_drafted",
        lead_id=lead_id,
        company=lead["company"],
        hook_tier=result.hook_tier_used,
        length=len(result.body),
    )
    return result


def draft_dm(lead_id: str) -> _LinkedInResult:
    """Generate the first DM after an invite has been accepted.

    Requires: linkedin_state = 'connected'. Reads the prior invite note
    (if any) so the DM doesn't repeat the exact hook verbatim.
    """
    lead_resp = (
        supabase.table("leads").select("*").eq("id", lead_id).single().execute()
    )
    lead = lead_resp.data

    if lead.get("linkedin_state") != "connected":
        raise LinkedInDraftError(
            f"Lead {lead_id} has linkedin_state={lead.get('linkedin_state')!r}; "
            f"DM requires 'connected'"
        )
    if lead.get("status") == "unsubscribed":
        raise LinkedInDraftError(f"Lead {lead_id} is unsubscribed")

    # Pull the invite note we sent (if any) so we don't repeat the hook.
    invite_resp = (
        supabase.table("messages")
        .select("body")
        .eq("lead_id", lead_id)
        .eq("channel", "linkedin_invite")
        .eq("direction", "outbound")
        .not_.is_("sent_at", "null")
        .order("sent_at", desc=True)
        .limit(1)
        .execute()
    )
    invite_note = invite_resp.data[0]["body"] if invite_resp.data else None

    sender_name, sender_title = _load_sender()
    available_tiers = compute_available_tiers(lead)
    sample_email = _load_sample_email(lead)
    intel = lead.get("intel_json") or {}

    prompt = DM_TEMPLATE.render(
        sender_name=sender_name,
        sender_title=sender_title,
        company=lead["company"],
        city=lead["city"],
        owner_name=lead.get("owner_name"),
        google_rating=lead.get("google_rating"),
        google_reviews=lead.get("google_reviews"),
        intel=intel,
        invite_note=invite_note,
        available_tiers=available_tiers,
        tier_descriptions=TIER_NAMES,
        sample_email=sample_email,
        knowledge_base=load_knowledge_base(),
    )

    result = gemini.generate_json_pro(prompt, _LinkedInResult)

    _replace_pending_draft(lead_id, "linkedin_dm")
    supabase.table("messages").insert(
        {
            "lead_id": lead_id,
            "direction": "outbound",
            "channel": "linkedin_dm",
            "provider": "unipile",
            "subject": None,
            "body": result.body,
            "hook_tier_used": result.hook_tier_used,
            "hook_text": result.hook_text,
            "hook_rationale": result.hook_rationale,
        }
    ).execute()

    log.info(
        "linkedin_dm_drafted",
        lead_id=lead_id,
        company=lead["company"],
        hook_tier=result.hook_tier_used,
        length=len(result.body),
    )
    return result


def draft_for_kind(lead_id: str, kind: Literal["invite", "dm"]) -> _LinkedInResult:
    """Convenience dispatcher for the API route + manual scripts."""
    if kind == "invite":
        return draft_invite(lead_id)
    if kind == "dm":
        return draft_dm(lead_id)
    raise LinkedInDraftError(f"unknown kind: {kind!r}")
