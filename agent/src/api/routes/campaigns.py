from datetime import datetime, timedelta, timezone
from typing import Literal

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent.src.api.deps import CurrentUser
from agent.src.clients.supabase_client import supabase
from agent.src.functions.campaign_runner import (
    run_all_active_campaigns,
    run_campaign_tick,
)

log = structlog.get_logger(__name__)

router = APIRouter()


class CreateCampaignBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=200)
    sample_email: str | None = None
    autonomy: Literal["full", "review_drafts"] = "full"
    daily_send_cap: int = Field(default=15, ge=1, le=500)
    total_lead_cap: int | None = Field(default=None, ge=1, le=5000)


class PatchCampaignBody(BaseModel):
    status: Literal["active", "paused", "archived"] | None = None
    autonomy: Literal["full", "review_drafts"] | None = None
    sample_email: str | None = None


def _campaign_metrics(campaign_id: str) -> dict:
    """Derived metrics for a campaign. Source of truth = leads + messages."""
    leads_resp = (
        supabase.table("leads")
        .select("id, status")
        .eq("campaign_id", campaign_id)
        .execute()
    )
    leads = leads_resp.data
    status_counts: dict[str, int] = {}
    for row in leads:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    lead_ids = [r["id"] for r in leads]
    sent_today = 0
    sent_total = 0
    if lead_ids:
        today = datetime.now(timezone.utc).date().isoformat()
        sent_total_resp = (
            supabase.table("messages")
            .select("id", count="exact")
            .eq("direction", "outbound")
            .eq("is_test", False)
            .in_("lead_id", lead_ids)
            .not_.is_("sent_at", "null")
            .execute()
        )
        sent_total = sent_total_resp.count or 0

        sent_today_resp = (
            supabase.table("messages")
            .select("id", count="exact")
            .eq("direction", "outbound")
            .eq("is_test", False)
            .in_("lead_id", lead_ids)
            .gte("sent_at", today)
            .execute()
        )
        sent_today = sent_today_resp.count or 0

    replied = status_counts.get("replied", 0) + status_counts.get("booked", 0)
    booked = status_counts.get("booked", 0)

    reply_rate = replied / sent_total if sent_total else 0.0
    book_rate = booked / sent_total if sent_total else 0.0

    # 14-day send series for the campaign list sparkline. Oldest day first,
    # today last. All zero if the campaign has no sends.
    sends_14: list[int] = [0] * 14
    if lead_ids:
        window_start = (
            datetime.now(timezone.utc) - timedelta(days=13)
        ).date()
        resp = (
            supabase.table("messages")
            .select("sent_at")
            .eq("direction", "outbound")
            .eq("is_test", False)
            .in_("lead_id", lead_ids)
            .gte("sent_at", window_start.isoformat())
            .execute()
        )
        today = datetime.now(timezone.utc).date()
        for row in resp.data or []:
            sent = row.get("sent_at")
            if not sent:
                continue
            day = datetime.fromisoformat(sent.replace("Z", "+00:00")).date()
            idx = 13 - (today - day).days
            if 0 <= idx < 14:
                sends_14[idx] += 1

    return {
        "leads_total": len(leads),
        "status_counts": status_counts,
        "sent_total": sent_total,
        "sent_today": sent_today,
        "replied": replied,
        "booked": booked,
        "reply_rate": round(reply_rate, 4),
        "book_rate": round(book_rate, 4),
        "sends_last_14_days": sends_14,
    }


@router.get("")
def list_campaigns(_user: CurrentUser):
    """List all campaigns with derived metrics attached to each."""
    resp = (
        supabase.table("campaigns")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    result = []
    for row in resp.data:
        row["metrics"] = _campaign_metrics(row["id"])
        result.append(row)
    return result


@router.post("")
def create_campaign(_user: CurrentUser, body: CreateCampaignBody):
    insert_resp = (
        supabase.table("campaigns")
        .insert(
            {
                "name": body.name,
                "city": body.city,
                "target": body.target,
                "sample_email": body.sample_email,
                "autonomy": body.autonomy,
                "daily_send_cap": body.daily_send_cap,
                "total_lead_cap": body.total_lead_cap,
            }
        )
        .execute()
    )
    campaign = insert_resp.data[0]
    campaign["metrics"] = _campaign_metrics(campaign["id"])
    log.info("campaign_created", campaign_id=campaign["id"], name=body.name)
    return campaign


@router.get("/{campaign_id}")
def get_campaign(_user: CurrentUser, campaign_id: str):
    resp = (
        supabase.table("campaigns")
        .select("*")
        .eq("id", campaign_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "Campaign not found")
    campaign = resp.data[0]
    campaign["metrics"] = _campaign_metrics(campaign_id)
    return campaign


@router.patch("/{campaign_id}")
def patch_campaign(_user: CurrentUser, campaign_id: str, body: PatchCampaignBody):
    update: dict = {}
    if body.status is not None:
        update["status"] = body.status
    if body.autonomy is not None:
        update["autonomy"] = body.autonomy
    if body.sample_email is not None:
        update["sample_email"] = body.sample_email
    if not update:
        raise HTTPException(400, "No fields to update")

    resp = (
        supabase.table("campaigns")
        .update(update)
        .eq("id", campaign_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "Campaign not found")
    campaign = resp.data[0]
    campaign["metrics"] = _campaign_metrics(campaign_id)
    log.info("campaign_updated", campaign_id=campaign_id, fields=list(update.keys()))
    return campaign


@router.get("/{campaign_id}/leads")
def campaign_leads(_user: CurrentUser, campaign_id: str, limit: int = 100):
    limit = min(limit, 500)
    resp = (
        supabase.table("leads")
        .select(
            "id, company, city, email, status, owner_name, "
            "google_rating, google_reviews, created_at, updated_at"
        )
        .eq("campaign_id", campaign_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data


@router.post("/{campaign_id}/tick")
def campaign_tick(_user: CurrentUser, campaign_id: str):
    """Manually advance a campaign one tick. Safe under the lock."""
    return run_campaign_tick(campaign_id)


@router.post("/tick-all")
def campaign_tick_all(_user: CurrentUser):
    """Tick every active campaign. Same code path as the cron CLI."""
    return {"results": run_all_active_campaigns()}
