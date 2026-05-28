from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.src.api.deps import CurrentUser
from agent.src.clients.supabase_client import supabase

router = APIRouter()


def _today_midnight_utc() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _annotate(raw: list[dict]) -> list[dict]:
    """Add sent_today, utilization_pct, and status to each inbox row."""
    today = _today_midnight_utc()
    result = []
    for row in raw:
        count_resp = (
            supabase.table("messages")
            .select("id", count="exact")
            .eq("inbox_id", row["id"])
            .eq("direction", "outbound")
            .not_.is_("sent_at", "null")
            .gte("sent_at", today)
            .execute()
        )
        sent_today = count_resp.count or 0
        limit = row["daily_send_limit"]
        utilization_pct = round(sent_today / limit * 100, 1) if limit > 0 else 0.0

        if utilization_pct >= 100:
            status = "blocked"
        elif utilization_pct >= 75:
            status = "warning"
        else:
            status = "ok"

        result.append({**row, "sent_today": sent_today, "utilization_pct": utilization_pct, "status": status})
    return result


class CreateInboxBody(BaseModel):
    email: str
    agentmail_inbox_id: str
    daily_send_limit: int = 40


class UpdateInboxBody(BaseModel):
    email: str | None = None
    daily_send_limit: int | None = None
    is_active: bool | None = None


# /capacity must be registered before /{inbox_id} so FastAPI does not treat
# the literal string "capacity" as a path parameter value.
@router.get("/capacity")
def get_inbox_capacity(_user: CurrentUser):
    """Convenience alias for GET /api/inboxes. Same shape — for the dashboard widget."""
    raw = supabase.table("inboxes").select("*").order("created_at").execute()
    return _annotate(raw.data)


@router.get("")
def list_inboxes(_user: CurrentUser):
    """List all inboxes with sent_today, utilization_pct, and status."""
    raw = supabase.table("inboxes").select("*").order("created_at").execute()
    return _annotate(raw.data)


@router.post("", status_code=201)
def create_inbox(_user: CurrentUser, body: CreateInboxBody):
    """Register a new inbox."""
    if body.daily_send_limit < 1:
        raise HTTPException(400, "daily_send_limit must be at least 1")
    resp = (
        supabase.table("inboxes")
        .insert({
            "email": body.email.strip().lower(),
            "agentmail_inbox_id": body.agentmail_inbox_id.strip(),
            "daily_send_limit": body.daily_send_limit,
        })
        .execute()
    )
    return resp.data[0]


@router.patch("/{inbox_id}")
def update_inbox(_user: CurrentUser, inbox_id: str, body: UpdateInboxBody):
    """Update email, daily_send_limit, or is_active on an inbox."""
    patch: dict = {}
    if body.email is not None:
        patch["email"] = body.email.strip().lower()
    if body.daily_send_limit is not None:
        if body.daily_send_limit < 1:
            raise HTTPException(400, "daily_send_limit must be at least 1")
        patch["daily_send_limit"] = body.daily_send_limit
    if body.is_active is not None:
        patch["is_active"] = body.is_active
    if not patch:
        raise HTTPException(400, "No fields to update")
    resp = (
        supabase.table("inboxes")
        .update(patch)
        .eq("id", inbox_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "Inbox not found")
    return resp.data[0]


@router.delete("/{inbox_id}", status_code=204)
def delete_inbox(_user: CurrentUser, inbox_id: str):
    """Soft delete: set is_active=false. Row is kept for historical attribution."""
    resp = (
        supabase.table("inboxes")
        .update({"is_active": False})
        .eq("id", inbox_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "Inbox not found")
