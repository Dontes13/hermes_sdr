"""LinkedIn follow-up scheduler.

Runs inside `run_campaign_tick`. Two queues per tick:

  1. INVITES — leads where:
        linkedin_followup_eligible_at <= now()
        AND linkedin_state IS NULL
        AND linkedin_url IS NOT NULL
        AND status IN ('sent')         (email was sent, no reply yet)
        AND no inbound email exists    (race-safe re-check)
        AND not unsubscribed

     For each, draft a `linkedin_invite` message. Auto-send only if the
     campaign autonomy is 'full' AND we're under the daily LinkedIn cap.

  2. DMs — leads where:
        linkedin_state = 'connected'
        AND no pending or sent linkedin_dm message exists
        AND not unsubscribed

     Draft a `linkedin_dm`. Same auto-send gating.

Sends are gated by:
  - LINKEDIN_MAX_DAILY_SENDS (system-wide ceiling, env)
  - LINKEDIN_DRAFT_PER_TICK / LINKEDIN_SEND_PER_TICK (per-tick caps, env)

Counts only non-test outbound LinkedIn messages toward the daily total.
"""

from datetime import datetime, timezone
from typing import Optional

import structlog

from agent.src.clients.supabase_client import supabase
from agent.src.config import settings
from agent.src.functions.draft_linkedin import draft_dm, draft_invite

log = structlog.get_logger(__name__)


def _today_linkedin_sent_count() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    resp = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("direction", "outbound")
        .eq("is_test", False)
        .in_("channel", ["linkedin_invite", "linkedin_dm"])
        .gte("sent_at", today)
        .execute()
    )
    return resp.count or 0


def _has_inbound_email(lead_id: str) -> bool:
    """Re-check at scheduler time: did the prospect reply to the email?

    If yes, don't queue a LinkedIn invite — the email cadence took over.
    Filtered to channel='email' so a future LinkedIn DM doesn't suppress
    LinkedIn invites (it shouldn't anyway since invite would already be
    sent first, but be explicit).
    """
    resp = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("lead_id", lead_id)
        .eq("direction", "inbound")
        .eq("channel", "email")
        .limit(1)
        .execute()
    )
    return (resp.count or 0) > 0


def _has_pending_or_sent(lead_id: str, channel: str) -> bool:
    resp = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("lead_id", lead_id)
        .eq("channel", channel)
        .eq("direction", "outbound")
        .limit(1)
        .execute()
    )
    return (resp.count or 0) > 0


def run_linkedin_followup(
    *,
    campaign_id: Optional[str] = None,
    autonomy: str = "full",
) -> dict:
    """Tick the LinkedIn cadence.

    campaign_id: when provided, restrict to leads in that campaign. None
    means "all eligible leads" (used by the daily cron).

    autonomy: 'full' = also auto-send drafts up to the daily cap.
              'review_drafts' = draft only; operator approves via /approvals.

    Returns a summary dict.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    summary = {
        "invites_drafted": 0,
        "invites_sent": 0,
        "dms_drafted": 0,
        "dms_sent": 0,
        "errors": [],
    }

    # ── 1. Queue invites ──
    invite_q = (
        supabase.table("leads")
        .select("id, company")
        .eq("status", "sent")
        .is_("linkedin_state", "null")
        .not_.is_("linkedin_url", "null")
        .lte("linkedin_followup_eligible_at", now_iso)
        .limit(settings.LINKEDIN_DRAFT_PER_TICK)
    )
    if campaign_id:
        invite_q = invite_q.eq("campaign_id", campaign_id)
    invite_candidates = invite_q.execute().data

    for row in invite_candidates:
        if _has_inbound_email(row["id"]):
            # Stale read — they replied since the eligibility timestamp was
            # set. Clear the stamp so we don't keep scanning this lead.
            supabase.table("leads").update(
                {"linkedin_followup_eligible_at": None}
            ).eq("id", row["id"]).execute()
            continue
        if _has_pending_or_sent(row["id"], "linkedin_invite"):
            continue
        try:
            draft_invite(row["id"])
            summary["invites_drafted"] += 1
        except Exception as e:
            log.warning(
                "linkedin_invite_draft_error",
                lead_id=row["id"],
                error=str(e),
            )
            summary["errors"].append(f"invite_draft {row['id']}: {e}")

    # ── 2. Queue DMs (newly connected leads) ──
    dm_q = (
        supabase.table("leads")
        .select("id, company")
        .eq("linkedin_state", "connected")
        .limit(settings.LINKEDIN_DRAFT_PER_TICK)
    )
    if campaign_id:
        dm_q = dm_q.eq("campaign_id", campaign_id)
    dm_candidates = dm_q.execute().data

    for row in dm_candidates:
        if _has_pending_or_sent(row["id"], "linkedin_dm"):
            continue
        try:
            draft_dm(row["id"])
            summary["dms_drafted"] += 1
        except Exception as e:
            log.warning(
                "linkedin_dm_draft_error",
                lead_id=row["id"],
                error=str(e),
            )
            summary["errors"].append(f"dm_draft {row['id']}: {e}")

    # ── 3. Auto-send (only if autonomy='full') ──
    if autonomy != "full":
        log.info("linkedin_tick_drafts_only", **summary)
        return summary

    today_sent = _today_linkedin_sent_count()
    remaining = settings.LINKEDIN_MAX_DAILY_SENDS - today_sent
    if remaining <= 0:
        log.warning(
            "linkedin_send_blocked_daily_cap",
            today_sent=today_sent,
            ceiling=settings.LINKEDIN_MAX_DAILY_SENDS,
        )
        summary["skipped_daily_cap"] = True
        return summary

    # Find pending LinkedIn drafts (any channel) that belong to this
    # campaign (or all, if campaign_id is None).
    sendable_q = (
        supabase.table("messages")
        .select("id, lead_id, channel")
        .eq("direction", "outbound")
        .in_("channel", ["linkedin_invite", "linkedin_dm"])
        .is_("sent_at", "null")
        .order("created_at", desc=False)
        .limit(min(remaining, settings.LINKEDIN_SEND_PER_TICK))
    )
    if campaign_id:
        # Inner-filter by campaign via a subquery — Postgrest doesn't let us
        # join, so pull lead ids first.
        scoped_leads = (
            supabase.table("leads")
            .select("id")
            .eq("campaign_id", campaign_id)
            .execute()
        )
        ids = [r["id"] for r in scoped_leads.data]
        if not ids:
            return summary
        sendable_q = sendable_q.in_("lead_id", ids)
    pending = sendable_q.execute().data

    # Lazy import — sending pulls the unipile client which requires real env.
    from agent.src.functions.send_linkedin import send_linkedin

    for m in pending:
        try:
            send_linkedin(m["id"])
            if m["channel"] == "linkedin_invite":
                summary["invites_sent"] += 1
            else:
                summary["dms_sent"] += 1
        except Exception as e:
            log.warning(
                "linkedin_send_error",
                message_id=m["id"],
                lead_id=m["lead_id"],
                channel=m["channel"],
                error=str(e),
            )
            summary["errors"].append(f"send {m['id']}: {e}")

    log.info("linkedin_tick_complete", **summary)
    return summary
