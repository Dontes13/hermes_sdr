"""Campaign tick runner.

A campaign progresses through prospect → enrich → draft → send per tick.
Ticks are serialized per campaign via a conditional-UPDATE advisory lock on
the `tick_running_at` column. The 10-minute stale-lock timeout lets a new
tick reclaim a lock left behind by a crashed worker.

A system-wide daily send ceiling (HERMES_MAX_DAILY_SENDS) backstops bad
targets / uncapped total_lead_cap configurations.
"""

from datetime import datetime, timedelta, timezone

import structlog

from agent.src.clients.supabase_client import supabase
from agent.src.config import settings
from agent.src.functions.draft import draft
from agent.src.functions.enrich import enrich
from agent.src.functions.linkedin_followup_scheduler import run_linkedin_followup
from agent.src.functions.prospect import prospect
from agent.src.functions.send import send

log = structlog.get_logger(__name__)

# Per-tick caps — a single tick won't do more work than this even if the
# backlog is larger. Keeps tick latency bounded.
PROSPECT_PER_TICK = 5
ENRICH_PER_TICK = 10
DRAFT_PER_TICK = 10
SEND_PER_TICK = 10


def _today_sent_count_for_campaign(campaign_id: str) -> int:
    """Count outbound messages sent today for leads in this campaign."""
    today = datetime.now(timezone.utc).date().isoformat()
    # Pull lead ids for the campaign
    leads_resp = (
        supabase.table("leads")
        .select("id")
        .eq("campaign_id", campaign_id)
        .execute()
    )
    lead_ids = [row["id"] for row in leads_resp.data]
    if not lead_ids:
        return 0
    resp = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("direction", "outbound")
        .eq("is_test", False)
        .in_("lead_id", lead_ids)
        .gte("sent_at", today)
        .execute()
    )
    return resp.count or 0


def _today_sent_count_global() -> int:
    """Count outbound messages sent today across all campaigns."""
    today = datetime.now(timezone.utc).date().isoformat()
    resp = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("direction", "outbound")
        .eq("is_test", False)
        .gte("sent_at", today)
        .execute()
    )
    return resp.count or 0


STALE_LOCK_SECONDS = 600


def _try_acquire_lock(campaign_id: str) -> dict | None:
    """Atomic lock acquisition via conditional UPDATE.

    Sets tick_running_at = now() iff it is NULL or stale
    (older than STALE_LOCK_SECONDS). PostgREST evaluates the .or_() filter
    atomically as part of the UPDATE, so two racing ticks cannot both
    succeed — the first UPDATE commits and the second's WHERE clause no
    longer matches.

    Returns the updated row on success, None if another tick owns the lock.
    """
    now = datetime.now(timezone.utc)
    stale_cutoff = (now - timedelta(seconds=STALE_LOCK_SECONDS)).isoformat()
    resp = (
        supabase.table("campaigns")
        .update({"tick_running_at": now.isoformat()})
        .eq("id", campaign_id)
        .or_(f"tick_running_at.is.null,tick_running_at.lt.{stale_cutoff}")
        .execute()
    )
    if not resp.data:
        return None
    return resp.data[0]


def _release_lock(campaign_id: str) -> None:
    supabase.table("campaigns").update({"tick_running_at": None}).eq(
        "id", campaign_id
    ).execute()


def run_campaign_tick(campaign_id: str) -> dict:
    """Advance a single campaign one step.

    Returns a summary dict. Safe to call concurrently — the lock ensures
    only one tick runs per campaign at a time.
    """
    campaign = _try_acquire_lock(campaign_id)
    if campaign is None:
        log.info("campaign_tick_skipped_lock_held", campaign_id=campaign_id)
        return {"skipped": "lock_held", "campaign_id": campaign_id}

    summary: dict = {
        "campaign_id": campaign_id,
        "prospected": 0,
        "enriched": 0,
        "dead": 0,
        "drafted": 0,
        "sent": 0,
        "errors": [],
    }

    try:
        if campaign["status"] != "active":
            return {**summary, "skipped": f"status={campaign['status']}"}

        # Derived counts (source of truth = leads table)
        leads_resp = (
            supabase.table("leads")
            .select("id, status")
            .eq("campaign_id", campaign_id)
            .execute()
        )
        all_leads = leads_resp.data
        status_counts: dict[str, int] = {}
        for row in all_leads:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        leads_prospected = len(all_leads)
        leads_sent = status_counts.get("sent", 0) + status_counts.get("replied", 0) + status_counts.get("booked", 0)

        total_cap = campaign.get("total_lead_cap")
        city = campaign["city"]
        target = campaign["target"]

        # 1. Prospect — only if under total_lead_cap
        if total_cap is None or leads_prospected < total_cap:
            remaining = PROSPECT_PER_TICK
            if total_cap is not None:
                remaining = min(remaining, total_cap - leads_prospected)
            if remaining > 0:
                try:
                    new_ids = prospect(
                        city=city,
                        max_leads=remaining,
                        target=target,
                        campaign_id=campaign_id,
                    )
                    summary["prospected"] = len(new_ids)
                except Exception as e:
                    log.warning(
                        "campaign_prospect_error", campaign_id=campaign_id, error=str(e)
                    )
                    summary["errors"].append(f"prospect: {e}")

        # 2. Enrich all status='new' leads in this campaign
        new_leads = (
            supabase.table("leads")
            .select("id")
            .eq("campaign_id", campaign_id)
            .eq("status", "new")
            .limit(ENRICH_PER_TICK)
            .execute()
        )
        for row in new_leads.data:
            try:
                result = enrich(row["id"])
                if result:
                    summary["enriched"] += 1
                else:
                    summary["dead"] += 1
            except Exception as e:
                log.warning(
                    "campaign_enrich_error",
                    campaign_id=campaign_id,
                    lead_id=row["id"],
                    error=str(e),
                )
                summary["errors"].append(f"enrich {row['id']}: {e}")

        # 3. Draft all status='enriched' leads. sample_email is pulled
        # automatically inside draft() via the campaign relation.
        enriched_leads = (
            supabase.table("leads")
            .select("id")
            .eq("campaign_id", campaign_id)
            .eq("status", "enriched")
            .limit(DRAFT_PER_TICK)
            .execute()
        )
        for row in enriched_leads.data:
            try:
                draft(row["id"])
                summary["drafted"] += 1
            except Exception as e:
                log.warning(
                    "campaign_draft_error",
                    campaign_id=campaign_id,
                    lead_id=row["id"],
                    error=str(e),
                )
                summary["errors"].append(f"draft {row['id']}: {e}")

        # 4. Send — only if autonomy='full'. Skip for review_drafts mode.
        if campaign["autonomy"] == "full":
            today_sent = _today_sent_count_for_campaign(campaign_id)
            remaining_today = campaign["daily_send_cap"] - today_sent
            if remaining_today > 0:
                # System-wide backstop
                global_today = _today_sent_count_global()
                global_remaining = settings.HERMES_MAX_DAILY_SENDS - global_today
                if global_remaining <= 0:
                    log.warning(
                        "campaign_send_blocked_global_cap",
                        campaign_id=campaign_id,
                        global_today=global_today,
                        ceiling=settings.HERMES_MAX_DAILY_SENDS,
                    )
                    summary["skipped_global_cap"] = True
                else:
                    drafts = (
                        supabase.table("leads")
                        .select("id")
                        .eq("campaign_id", campaign_id)
                        .eq("status", "drafted")
                        .limit(min(remaining_today, SEND_PER_TICK, global_remaining))
                        .execute()
                    )
                    for row in drafts.data:
                        # Fetch the pending message for this lead
                        msg = (
                            supabase.table("messages")
                            .select("id")
                            .eq("lead_id", row["id"])
                            .eq("direction", "outbound")
                            .is_("sent_at", "null")
                            .limit(1)
                            .execute()
                        )
                        if not msg.data:
                            continue
                        try:
                            send(msg.data[0]["id"])
                            summary["sent"] += 1
                        except Exception as e:
                            log.warning(
                                "campaign_send_error",
                                campaign_id=campaign_id,
                                lead_id=row["id"],
                                error=str(e),
                            )
                            summary["errors"].append(f"send {row['id']}: {e}")

        # 4b. LinkedIn follow-up — drafts invites for unanswered leads past
        # their cooling period and DMs for newly-connected ones. Auto-send
        # follows campaign autonomy and a separate daily cap.
        try:
            li_summary = run_linkedin_followup(
                campaign_id=campaign_id,
                autonomy=campaign["autonomy"],
            )
            summary["linkedin"] = {
                k: v for k, v in li_summary.items() if k != "errors"
            }
            if li_summary.get("errors"):
                summary["errors"].extend(li_summary["errors"])
        except Exception as e:
            log.warning(
                "campaign_linkedin_error", campaign_id=campaign_id, error=str(e)
            )
            summary["errors"].append(f"linkedin: {e}")

        # 5. Completion check — cap reached and nothing in flight
        if total_cap is not None:
            fresh = (
                supabase.table("leads")
                .select("id, status")
                .eq("campaign_id", campaign_id)
                .execute()
            )
            in_flight_statuses = {"new", "enriched", "drafted", "approved"}
            in_flight = sum(1 for r in fresh.data if r["status"] in in_flight_statuses)
            if len(fresh.data) >= total_cap and in_flight == 0:
                supabase.table("campaigns").update({"status": "completed"}).eq(
                    "id", campaign_id
                ).execute()
                summary["marked_completed"] = True

        log.info("campaign_tick_complete", **summary)
        return summary

    finally:
        _release_lock(campaign_id)


def run_all_active_campaigns() -> list[dict]:
    """Tick every active campaign. Called from the CLI / cron."""
    resp = (
        supabase.table("campaigns")
        .select("id, name")
        .eq("status", "active")
        .execute()
    )
    results: list[dict] = []
    for row in resp.data:
        summary = run_campaign_tick(row["id"])
        summary["name"] = row["name"]
        results.append(summary)
    return results
