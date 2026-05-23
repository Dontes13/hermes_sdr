import random
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
SUBJECT_TEMPLATE = Template(
    (Path(__file__).parent.parent / "prompts" / "subject.j2").read_text()
)

_FALLBACK_SUBJECT_PROMPT = (
    "Generate a short subject line (3–6 words, all lowercase) for a cold outreach email. "
    "Reference something specific to this prospect — their company, market, or reputation. "
    "No emojis. No clickbait. Should feel like a personal note from one person to another."
)


class BodyResult(BaseModel):
    body: str
    hook_tier_used: int
    hook_text: str
    hook_rationale: str


class SubjectResult(BaseModel):
    subject: str


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

    # 3a. Select subject line variant for A/B testing.
    # 50/50 random assignment; assignment is fixed at draft time for each lead.
    variants_resp = (
        supabase.table("subject_variants")
        .select("id, name, subject_prompt")
        .eq("is_active", True)
        .execute()
    )
    variants = variants_resp.data or []
    if not variants:
        log.warning("no_active_subject_variants", lead_id=lead_id)
        chosen_variant: dict | None = None
    elif len(variants) == 1:
        chosen_variant = variants[0]
    else:
        chosen_variant = random.choice(variants)

    subject_prompt_text = (
        chosen_variant["subject_prompt"] if chosen_variant else _FALLBACK_SUBJECT_PROMPT
    )

    # 4. Render body prompt
    intel = lead.get("intel_json") or {}
    apollo = intel.get("apollo") or {}
    apollo_contact = apollo.get("contact") or {}
    apollo_org = apollo.get("org") or {}

    body_prompt = DRAFT_TEMPLATE.render(
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
        apollo_title=apollo_contact.get("title"),
        apollo_headcount=apollo_org.get("headcount"),
        apollo_tenure_start=apollo_contact.get("tenure_start"),
    )

    # 5. Call Gemini Pro for body + hook (hook tier selection happens here)
    body_result: BodyResult = gemini.generate_json_pro(body_prompt, BodyResult)

    # 6. Validate hook_tier_used — one correction retry if invalid
    if body_result.hook_tier_used not in available_tiers:
        log.warning(
            "draft_invalid_tier",
            lead_id=lead_id,
            attempted_tier=body_result.hook_tier_used,
            available=available_tiers,
        )
        corrective_prompt = (
            body_prompt
            + f"\n\nCORRECTION: Your previous response chose tier "
            f"{body_result.hook_tier_used}, which is not in the available list "
            f"{available_tiers}. The lowest-numbered (highest-quality) "
            f"available tier is {min(available_tiers)}. You MUST choose a "
            f"tier from {available_tiers}. Try again."
        )
        body_result2: BodyResult = gemini.generate_json_pro(
            corrective_prompt, BodyResult
        )
        if body_result2.hook_tier_used not in available_tiers:
            log.warning(
                "draft_invalid_tier_second_attempt",
                lead_id=lead_id,
                first_tier=body_result.hook_tier_used,
                second_tier=body_result2.hook_tier_used,
                available=available_tiers,
            )
        body_result = body_result2

    # 7. Generate subject line using chosen variant prompt + hook context.
    # Subject is generated after body so it can reference the chosen hook.
    subject_prompt = SUBJECT_TEMPLATE.render(
        sender_name=sender_name,
        sender_title=sender_title,
        subject_prompt=subject_prompt_text,
        company=lead["company"],
        city=lead["city"],
        google_rating=lead.get("google_rating"),
        google_reviews=lead.get("google_reviews"),
        intel=intel,
        hook_tier_used=body_result.hook_tier_used,
        hook_text=body_result.hook_text,
        tier_description=TIER_NAMES.get(body_result.hook_tier_used, ""),
    )
    subject_result: SubjectResult = gemini.generate_json_pro(
        subject_prompt, SubjectResult
    )

    # 8. If redraft, delete old outbound drafts first
    if lead["status"] == "drafted":
        (
            supabase.table("messages")
            .delete()
            .eq("lead_id", lead_id)
            .eq("direction", "outbound")
            .execute()
        )

    # 9. Insert new message with variant tracking
    supabase.table("messages").insert(
        {
            "lead_id": lead_id,
            "direction": "outbound",
            "subject": subject_result.subject,
            "body": body_result.body,
            "hook_tier_used": body_result.hook_tier_used,
            "hook_text": body_result.hook_text,
            "hook_rationale": body_result.hook_rationale,
            "subject_variant_id": chosen_variant["id"] if chosen_variant else None,
        }
    ).execute()

    # 10. Update lead status
    supabase.table("leads").update({"status": "drafted"}).eq(
        "id", lead_id
    ).execute()

    log.info(
        "draft_success",
        lead_id=lead_id,
        company=lead["company"],
        hook_tier=body_result.hook_tier_used,
        subject_variant=chosen_variant["name"] if chosen_variant else "fallback",
    )

    return DraftResult(
        subject=subject_result.subject,
        body=body_result.body,
        hook_tier_used=body_result.hook_tier_used,
        hook_text=body_result.hook_text,
        hook_rationale=body_result.hook_rationale,
    )
