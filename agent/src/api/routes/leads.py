from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.src.api.deps import CurrentUser
from agent.src.clients.supabase_client import supabase
from agent.src.exceptions import BriefError, LinkedInDraftError
from agent.src.functions.brief import brief
from agent.src.functions.draft import draft
from agent.src.functions.draft_linkedin import draft_for_kind
from agent.src.functions.send import send

router = APIRouter()

LEAD_SUMMARY_FIELDS = (
    "id, company, city, email, status, owner_name, "
    "google_rating, google_reviews, created_at, updated_at, "
    "icp_score, icp_score_reasons, vertical, source"
)


class EditBody(BaseModel):
    subject: str
    body: str


@router.get("")
def list_leads(
    _user: CurrentUser,
    status: str | None = None,
    limit: int = 50,
):
    """List leads with optional status filter.

    Each lead row is enriched with `latest_hook_tier`: the hook_tier_used
    of the most recent outbound message for that lead, or None if no
    drafted/sent outbound message exists yet. Enables server-side hook-
    tier filtering on the dashboard without an N+1 query.
    """
    limit = min(limit, 200)
    query = (
        supabase.table("leads")
        .select(LEAD_SUMMARY_FIELDS)
        .order("updated_at", desc=True)
        .limit(limit)
    )
    if status:
        query = query.eq("status", status)

    resp = query.execute()
    leads = resp.data

    if not leads:
        return leads

    lead_ids = [lead["id"] for lead in leads]
    msgs_resp = (
        supabase.table("messages")
        .select("lead_id, hook_tier_used, created_at")
        .in_("lead_id", lead_ids)
        .eq("direction", "outbound")
        .not_.is_("hook_tier_used", "null")
        .order("created_at", desc=True)
        .execute()
    )

    # Reduce to {lead_id: most_recent_hook_tier}. Rows are already sorted
    # desc so the first row per lead_id wins.
    tier_by_lead: dict[str, int] = {}
    for row in msgs_resp.data:
        lid = row["lead_id"]
        if lid not in tier_by_lead:
            tier_by_lead[lid] = row["hook_tier_used"]

    for lead in leads:
        lead["latest_hook_tier"] = tier_by_lead.get(lead["id"])

    return leads


@router.get("/{lead_id}")
def get_lead(_user: CurrentUser, lead_id: str):
    """Get full lead detail including all messages."""
    lead_resp = (
        supabase.table("leads").select("*").eq("id", lead_id).execute()
    )
    if not lead_resp.data:
        raise HTTPException(404, "Lead not found")

    messages_resp = (
        supabase.table("messages")
        .select("*")
        .eq("lead_id", lead_id)
        .order("created_at", desc=False)
        .execute()
    )

    return {"lead": lead_resp.data[0], "messages": messages_resp.data}


@router.post("/{lead_id}/approve")
def approve_lead(_user: CurrentUser, lead_id: str):
    """Send the pending outbound draft for this lead."""
    drafts = (
        supabase.table("messages")
        .select("*")
        .eq("lead_id", lead_id)
        .eq("direction", "outbound")
        .is_("sent_at", "null")
        .execute()
    )

    if not drafts.data:
        raise HTTPException(400, "No pending draft found for this lead")
    if len(drafts.data) > 1:
        raise HTTPException(
            400, "Multiple pending drafts, resolve manually"
        )

    message = drafts.data[0]
    send(message["id"])

    # Return updated lead
    lead_resp = (
        supabase.table("leads").select("*").eq("id", lead_id).single().execute()
    )
    return lead_resp.data


@router.post("/{lead_id}/skip")
def skip_lead(_user: CurrentUser, lead_id: str):
    """Mark lead as dead (skip). Does not delete the draft."""
    supabase.table("leads").update({"status": "dead"}).eq(
        "id", lead_id
    ).execute()
    return {"ok": True}


@router.post("/{lead_id}/regenerate")
def regenerate_lead(_user: CurrentUser, lead_id: str):
    """Regenerate the draft for this lead."""
    result = draft(lead_id)
    return result.model_dump()


@router.post("/{lead_id}/edit")
def edit_draft(_user: CurrentUser, lead_id: str, body: EditBody):
    """Edit the pending outbound draft's subject and body."""
    drafts = (
        supabase.table("messages")
        .select("*")
        .eq("lead_id", lead_id)
        .eq("direction", "outbound")
        .is_("sent_at", "null")
        .execute()
    )

    if not drafts.data:
        raise HTTPException(400, "No pending draft found for this lead")
    if len(drafts.data) > 1:
        raise HTTPException(
            400, "Multiple pending drafts, resolve manually"
        )

    message = drafts.data[0]
    supabase.table("messages").update(
        {"subject": body.subject, "body": body.body}
    ).eq("id", message["id"]).execute()

    updated = (
        supabase.table("messages")
        .select("*")
        .eq("id", message["id"])
        .single()
        .execute()
    )
    return updated.data


class LinkedInDraftBody(BaseModel):
    kind: Literal["invite", "dm"]


class LinkedInUrlBody(BaseModel):
    linkedin_url: Optional[str]  # null clears it


@router.post("/{lead_id}/linkedin/draft")
def draft_linkedin(
    _user: CurrentUser, lead_id: str, body: LinkedInDraftBody
):
    """Manually draft a LinkedIn invite or DM for a lead.

    Bypasses the cadence scheduler — operator chose this lead explicitly.
    The draft lands in the messages table as channel='linkedin_invite' or
    'linkedin_dm', sent_at=NULL, and shows up in the standard /approvals
    queue.
    """
    try:
        result = draft_for_kind(lead_id, body.kind)
    except LinkedInDraftError as e:
        raise HTTPException(400, str(e))
    return result.model_dump()


@router.put("/{lead_id}/linkedin-url")
def set_linkedin_url(
    _user: CurrentUser, lead_id: str, body: LinkedInUrlBody
):
    """Set or clear a lead's LinkedIn profile URL.

    Useful when enrichment didn't find the profile and the operator pastes
    it from the dashboard. No validation beyond non-empty — Unipile will
    reject malformed URLs at send time.
    """
    update_val = (body.linkedin_url or "").strip() or None
    supabase.table("leads").update({"linkedin_url": update_val}).eq(
        "id", lead_id
    ).execute()
    lead_resp = (
        supabase.table("leads").select("*").eq("id", lead_id).single().execute()
    )
    return lead_resp.data


@router.post("/{lead_id}/brief")
def generate_brief(_user: CurrentUser, lead_id: str):
    """Generate a pre-call briefing markdown for this lead.

    Stores it on the lead row and returns it. Flips status from 'replied' to
    'booked' if applicable.
    """
    try:
        briefing_md = brief(lead_id)
    except BriefError as e:
        raise HTTPException(500, f"briefing failed: {e}")
    return {"briefing_md": briefing_md}
