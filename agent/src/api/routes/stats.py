from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from agent.src.api.deps import CurrentUser
from agent.src.clients.supabase_client import supabase

router = APIRouter()


@router.get("")
def get_stats(_user: CurrentUser):
    """Dashboard stats: lead status counts, hook tier breakdown, last poll time."""
    counts = {
        "new": 0,
        "enriched": 0,
        "drafted": 0,
        "sent": 0,
        "replied": 0,
        "booked": 0,
        "dead": 0,
        "unsubscribed": 0,
    }

    # Fetch id+status in one pass so we can also derive the replied-lead id
    # set for the reply_drafts_pending count below.
    leads_resp = supabase.table("leads").select("id, status").execute()
    replied_lead_ids: list[str] = []
    for row in leads_resp.data:
        status = row["status"]
        if status in counts:
            counts[status] += 1
        if status == "replied":
            replied_lead_ids.append(row["id"])

    # Hook tier breakdown for sent messages (excludes test sends)
    hook_tiers_sent: dict[str, int] = {}
    msgs_resp = (
        supabase.table("messages")
        .select("hook_tier_used")
        .eq("direction", "outbound")
        .eq("is_test", False)
        .not_.is_("sent_at", "null")
        .execute()
    )
    for row in msgs_resp.data:
        tier = row.get("hook_tier_used")
        if tier is not None:
            key = str(tier)
            hook_tiers_sent[key] = hook_tiers_sent.get(key, 0) + 1

    # Last poll time
    sync_resp = (
        supabase.table("agentmail_sync")
        .select("last_polled_at")
        .eq("id", 1)
        .execute()
    )
    last_run_at = None
    if sync_resp.data:
        last_run_at = sync_resp.data[0].get("last_polled_at")

    # Pending reply drafts: outbound messages with sent_at IS NULL whose
    # lead is currently in 'replied' status. 2-query approach avoids the
    # supabase-py join syntax which is version-sensitive.
    reply_drafts_pending = 0
    if replied_lead_ids:
        pending_resp = (
            supabase.table("messages")
            .select("id", count="exact")
            .eq("direction", "outbound")
            .is_("sent_at", "null")
            .in_("lead_id", replied_lead_ids)
            .execute()
        )
        reply_drafts_pending = pending_resp.count or 0

    # Time-windowed activity for the hero tile. Cheap count queries.
    now = datetime.now(timezone.utc)
    today_iso = now.date().isoformat()
    week_iso = (now - timedelta(days=7)).isoformat()

    # All stats queries exclude is_test=true so test sends / test replies
    # don't inflate the funnel.
    sent_today = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("direction", "outbound")
        .eq("is_test", False)
        .gte("sent_at", today_iso)
        .execute()
        .count or 0
    )
    sent_week = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("direction", "outbound")
        .eq("is_test", False)
        .gte("sent_at", week_iso)
        .execute()
        .count or 0
    )
    inbound_week = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("direction", "inbound")
        .eq("is_test", False)
        .gte("created_at", week_iso)
        .execute()
        .count or 0
    )

    # Recent activity — last 8 outbound sends + inbound arrivals for the
    # pipeline activity feed. Excludes test traffic.
    recent_outbound = (
        supabase.table("messages")
        .select("id, lead_id, subject, sent_at, hook_tier_used")
        .eq("direction", "outbound")
        .eq("is_test", False)
        .not_.is_("sent_at", "null")
        .order("sent_at", desc=True)
        .limit(8)
        .execute()
    ).data or []
    recent_inbound = (
        supabase.table("messages")
        .select("id, lead_id, subject, created_at")
        .eq("direction", "inbound")
        .eq("is_test", False)
        .order("created_at", desc=True)
        .limit(8)
        .execute()
    ).data or []

    return {
        "counts": counts,
        "hook_tiers_sent": hook_tiers_sent,
        "last_run_at": last_run_at,
        "reply_drafts_pending": reply_drafts_pending,
        "sent_today": sent_today,
        "sent_week": sent_week,
        "inbound_week": inbound_week,
        "recent_outbound": recent_outbound,
        "recent_inbound": recent_inbound,
    }
