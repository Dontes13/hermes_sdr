from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.src.api.deps import CurrentUser
from agent.src.clients.supabase_client import supabase
from agent.src.exceptions import ReplyDraftError, SendError
from agent.src.functions.draft_reply import draft_reply
from agent.src.functions.send import send

router = APIRouter()


class EditReplyRequest(BaseModel):
    body: str


@router.get("")
def list_replies(_user: CurrentUser):
    """List every lead that has an inbound message on file.

    Covers both real replies (lead status='replied') AND test-thread replies
    where the lead status hasn't flipped. Each entry carries an `is_test`
    flag so the UI can distinguish them. Sorted by latest inbound DESC.
    """
    # Find every lead with at least one inbound
    inbound_lead_ids_resp = (
        supabase.table("messages")
        .select("lead_id")
        .eq("direction", "inbound")
        .execute()
    )
    lead_ids = list(
        {r["lead_id"] for r in (inbound_lead_ids_resp.data or [])}
    )
    if not lead_ids:
        return []

    leads_resp = (
        supabase.table("leads")
        .select("*")
        .in_("id", lead_ids)
        .execute()
    )

    results = []
    for lead in leads_resp.data:
        inbound = (
            supabase.table("messages")
            .select("*")
            .eq("lead_id", lead["id"])
            .eq("direction", "inbound")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        pending = (
            supabase.table("messages")
            .select("*")
            .eq("lead_id", lead["id"])
            .eq("direction", "outbound")
            .is_("sent_at", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        latest_inbound = inbound.data[0] if inbound.data else None
        results.append(
            {
                "lead": lead,
                "latest_inbound": latest_inbound,
                "pending_reply_draft": pending.data[0] if pending.data else None,
                "is_test": bool(latest_inbound and latest_inbound.get("is_test")),
            }
        )

    results.sort(
        key=lambda r: (r["latest_inbound"] or {}).get("created_at", ""),
        reverse=True,
    )
    return results


@router.post("/{lead_id}/approve")
def approve_reply(lead_id: str, _user: CurrentUser):
    """Send the pending reply draft for this lead."""
    pending = (
        supabase.table("messages")
        .select("*")
        .eq("lead_id", lead_id)
        .eq("direction", "outbound")
        .is_("sent_at", "null")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not pending.data:
        raise HTTPException(400, "no pending reply draft for this lead")

    try:
        result = send(pending.data[0]["id"])
    except SendError as e:
        raise HTTPException(500, f"send failed: {e}")

    return {"ok": True, "message_id": result.get("message_id")}


@router.post("/{lead_id}/edit")
def edit_reply(lead_id: str, body: EditReplyRequest, _user: CurrentUser):
    """Update the pending reply draft's body. No Gemini re-run."""
    pending = (
        supabase.table("messages")
        .select("id")
        .eq("lead_id", lead_id)
        .eq("direction", "outbound")
        .is_("sent_at", "null")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not pending.data:
        raise HTTPException(400, "no pending reply draft for this lead")

    supabase.table("messages").update({"body": body.body}).eq(
        "id", pending.data[0]["id"]
    ).execute()
    return {"ok": True}


@router.post("/{lead_id}/regenerate")
def regenerate_reply(lead_id: str, _user: CurrentUser):
    """Re-run draft_reply on the most recent inbound message for this lead."""
    latest_inbound = (
        supabase.table("messages")
        .select("id")
        .eq("lead_id", lead_id)
        .eq("direction", "inbound")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not latest_inbound.data:
        raise HTTPException(400, "no inbound message to reply to")

    try:
        result = draft_reply(latest_inbound.data[0]["id"])
    except ReplyDraftError as e:
        raise HTTPException(500, f"draft failed: {e}")

    return {"ok": True, "intent": result.intent}
