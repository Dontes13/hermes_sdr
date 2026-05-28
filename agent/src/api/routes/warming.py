from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.src.api.deps import CurrentUser
from agent.src.clients.supabase_client import supabase
from agent.src.services.warming import quota_for_day, run_warming_cycle

router = APIRouter()


class CreateScheduleBody(BaseModel):
    inbox_id: str
    target_daily_limit: int = 40


class PatchScheduleBody(BaseModel):
    status: Optional[str] = None
    target_daily_limit: Optional[int] = None


@router.get("")
def list_schedules(_user: CurrentUser):
    """List all warming schedules with their current state."""
    resp = (
        supabase.table("warming_schedule")
        .select("*, inboxes(email, display_name)")
        .order("created_at", desc=True)
        .execute()
    )
    schedules = resp.data or []
    for s in schedules:
        s["quota_today"] = quota_for_day(s["current_day"])
    return schedules


@router.post("")
def create_schedule(_user: CurrentUser, body: CreateScheduleBody):
    """Create a warming schedule for an inbox."""
    inbox_check = (
        supabase.table("inboxes")
        .select("id")
        .eq("id", body.inbox_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not inbox_check.data:
        raise HTTPException(404, "Inbox not found or inactive")

    existing = (
        supabase.table("warming_schedule")
        .select("id, status")
        .eq("inbox_id", body.inbox_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(409, "Warming schedule already exists for this inbox")

    resp = (
        supabase.table("warming_schedule")
        .insert(
            {
                "inbox_id": body.inbox_id,
                "target_daily_limit": body.target_daily_limit,
            }
        )
        .execute()
    )
    return resp.data[0]


@router.post("/run-now")
def run_now(_user: CurrentUser):
    """Manually trigger one warming cycle (no jitter). For testing only."""
    summary = run_warming_cycle(jitter=False)
    return summary


@router.patch("/{schedule_id}")
def patch_schedule(
    _user: CurrentUser, schedule_id: str, body: PatchScheduleBody
):
    """Update a warming schedule's status or target limit."""
    existing = (
        supabase.table("warming_schedule")
        .select("id")
        .eq("id", schedule_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(404, "Schedule not found")

    update: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if body.status is not None:
        allowed = {"warming", "complete", "paused"}
        if body.status not in allowed:
            raise HTTPException(400, f"status must be one of {allowed}")
        update["status"] = body.status
    if body.target_daily_limit is not None:
        update["target_daily_limit"] = body.target_daily_limit

    resp = (
        supabase.table("warming_schedule")
        .update(update)
        .eq("id", schedule_id)
        .execute()
    )
    return resp.data[0]


@router.delete("/{schedule_id}")
def delete_schedule(_user: CurrentUser, schedule_id: str):
    """Delete a warming schedule."""
    existing = (
        supabase.table("warming_schedule")
        .select("id")
        .eq("id", schedule_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(404, "Schedule not found")

    supabase.table("warming_schedule").delete().eq("id", schedule_id).execute()
    return {"ok": True}
