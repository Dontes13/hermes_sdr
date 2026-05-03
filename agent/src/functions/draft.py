from pathlib import Path

import structlog
from jinja2 import Template
from pydantic import BaseModel

from agent.src.clients.gemini import gemini
from agent.src.clients.supabase_client import supabase
from agent.src.functions.hook_tiers import TIER_NAMES, compute_available_tiers
from agent.src.functions.knowledge_base import load_knowledge_base

log = structlog.get_logger(__name__)

DRAFT_TEMPLATE = Template(
    (Path(__file__).parent.parent / "prompts" / "draft.j2").read_text()
)


class DraftResult(BaseModel):
    subject: str
    body: str
    hook_tier_used: int
    hook_text: str
    hook_rationale: str


def draft(lead_id: str, sample_email: str | None = None) -> DraftResult:
    """Generate cold email for an enriched lead. Store in messages table.

    sample_email: optional tone/voice reference. When provided, passed to
    the prompt as a style guide. Hook-tier rules remain authoritative.
    If not passed and the lead is attached to a campaign with a
    sample_email on file, the campaign's sample is used.
    """
    # 1. Load lead and validate status
    lead_resp = (
        supabase.table("leads").select("*").eq("id", lead_id).single().execute()
    )
    lead = lead_resp.data

    if lead["status"] not in ("enriched", "drafted"):
        raise ValueError(
            f"Lead {lead_id} has status '{lead['status']}', "
            f"expected 'enriched' or 'drafted'"
        )

    # 1a. Pull sample_email from the owning campaign if one wasn't passed.
    if sample_email is None and lead.get("campaign_id"):
        camp_resp = (
            supabase.table("campaigns")
            .select("sample_email")
            .eq("id", lead["campaign_id"])
            .limit(1)
            .execute()
        )
        if camp_resp.data:
            sample_email = camp_resp.data[0].get("sample_email")

    # 2. Compute available hook tiers
    available_tiers = compute_available_tiers(lead)

    # 3. Load sender info from config table (source of truth)
    config_resp = (
        supabase.table("config")
        .select("key, value")
        .in_("key", ["sender_name", "sender_title"])
        .execute()
    )
    config_map = {row["key"]: row["value"] for row in config_resp.data}
    sender_name = config_map.get("sender_name", "Enrique")
    sender_title = config_map.get("sender_title", "CTO, Helios Marketing")

    # 4. Render prompt
    intel = lead.get("intel_json") or {}
    prompt = DRAFT_TEMPLATE.render(
        sender_name=sender_name,
        sender_title=sender_title,
        company=lead["company"],
        city=lead["city"],
        google_rating=lead.get("google_rating"),
        google_reviews=lead.get("google_reviews"),
        intel=intel,
        available_tiers=available_tiers,
        tier_descriptions=TIER_NAMES,
        sample_email=sample_email,
        knowledge_base=load_knowledge_base(),
    )

    # 5. Call Gemini Pro
    result = gemini.generate_json_pro(prompt, DraftResult)

    # 6. Validate hook_tier_used — one correction retry if invalid
    if result.hook_tier_used not in available_tiers:
        log.warning(
            "draft_invalid_tier",
            lead_id=lead_id,
            attempted_tier=result.hook_tier_used,
            available=available_tiers,
        )
        corrective_prompt = (
            prompt
            + f"\n\nCORRECTION: Your previous response chose tier "
            f"{result.hook_tier_used}, which is not in the available list "
            f"{available_tiers}. The lowest-numbered (highest-quality) "
            f"available tier is {min(available_tiers)}. You MUST choose a "
            f"tier from {available_tiers}. Try again."
        )
        result2 = gemini.generate_json_pro(corrective_prompt, DraftResult)
        if result2.hook_tier_used not in available_tiers:
            log.warning(
                "draft_invalid_tier_second_attempt",
                lead_id=lead_id,
                first_tier=result.hook_tier_used,
                second_tier=result2.hook_tier_used,
                available=available_tiers,
            )
        result = result2

    # 7. If redraft, delete old outbound drafts first
    if lead["status"] == "drafted":
        (
            supabase.table("messages")
            .delete()
            .eq("lead_id", lead_id)
            .eq("direction", "outbound")
            .execute()
        )

    # 8. Insert new message
    supabase.table("messages").insert(
        {
            "lead_id": lead_id,
            "direction": "outbound",
            "subject": result.subject,
            "body": result.body,
            "hook_tier_used": result.hook_tier_used,
            "hook_text": result.hook_text,
            "hook_rationale": result.hook_rationale,
        }
    ).execute()

    # 9. Update lead status
    supabase.table("leads").update({"status": "drafted"}).eq(
        "id", lead_id
    ).execute()

    log.info(
        "draft_success",
        lead_id=lead_id,
        company=lead["company"],
        hook_tier=result.hook_tier_used,
    )

    return result
