"""Email warming service.

Progressively ramps per-inbox daily send volume according to the warming
schedule. All warming traffic is tracked in warming_sends, not messages.
poll.py handles reply detection for warming threads separately.
"""
import random
from datetime import datetime, timezone
from pathlib import Path

import structlog
from jinja2 import Template
from pydantic import BaseModel

from agent.src.clients.agentmail import agentmail_client
from agent.src.clients.gemini import gemini
from agent.src.clients.supabase_client import supabase
from agent.src.exceptions import AgentMailError

log = structlog.get_logger(__name__)

# Day → quota mapping. Days beyond the last key hold at the last value.
WARMING_SCHEDULE: dict[int, int] = {
    1: 5,
    2: 8,
    3: 10,
    4: 13,
    5: 16,
    6: 19,
    7: 22,
    8: 25,
    9: 28,
    10: 31,
    14: 35,
    21: 40,
}

_WARMING_TEMPLATE = Template(
    (Path(__file__).parent.parent / "prompts" / "warming.j2").read_text()
)


class WarmingEmail(BaseModel):
    subject: str
    body: str


def quota_for_day(day: int) -> int:
    """Return the target send quota for a given warming day."""
    last_quota = 5
    for d in sorted(WARMING_SCHEDULE):
        if day <= d:
            return WARMING_SCHEDULE[d]
        last_quota = WARMING_SCHEDULE[d]
    return last_quota


def _active_schedules() -> list[dict]:
    resp = (
        supabase.table("warming_schedule")
        .select("*")
        .eq("status", "warming")
        .execute()
    )
    return resp.data or []


def _inbox_details(inbox_uuid: str) -> dict | None:
    resp = (
        supabase.table("inboxes")
        .select("id, agentmail_inbox_id, email, display_name")
        .eq("id", inbox_uuid)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _all_active_inboxes() -> list[dict]:
    resp = (
        supabase.table("inboxes")
        .select("id, agentmail_inbox_id, email, display_name")
        .eq("is_active", True)
        .execute()
    )
    return resp.data or []


def _sent_today_count(inbox_uuid: str) -> int:
    today_utc = datetime.now(timezone.utc).date().isoformat()
    resp = (
        supabase.table("warming_sends")
        .select("id", count="exact")
        .eq("from_inbox_id", inbox_uuid)
        .gte("sent_at", today_utc)
        .execute()
    )
    return resp.count or 0


def _pick_peer(from_inbox_uuid: str, all_inboxes: list[dict]) -> dict | None:
    peers = [i for i in all_inboxes if i["id"] != from_inbox_uuid]
    return random.choice(peers) if peers else None


def _generate_warming_email(
    from_name: str, from_email: str, to_name: str, to_email: str
) -> WarmingEmail:
    prompt = _WARMING_TEMPLATE.render(
        from_name=from_name,
        from_email=from_email,
        to_name=to_name,
        to_email=to_email,
    )
    return gemini.generate_json_flash(prompt, WarmingEmail)


def _record_send(
    from_inbox_id: str,
    to_inbox_id: str,
    subject: str,
    body: str,
    provider_thread_id: str,
) -> None:
    supabase.table("warming_sends").insert(
        {
            "from_inbox_id": from_inbox_id,
            "to_inbox_id": to_inbox_id,
            "subject": subject,
            "body": body,
            "provider_thread_id": provider_thread_id,
        }
    ).execute()


def _advance_schedule(schedule: dict) -> None:
    new_day = schedule["current_day"] + 1
    update: dict = {
        "current_day": new_day,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    target = schedule.get("target_daily_limit", 40)
    if quota_for_day(new_day) >= target:
        update["status"] = "complete"
        log.info("warming_schedule_complete", inbox_id=schedule["inbox_id"])
    supabase.table("warming_schedule").update(update).eq(
        "id", schedule["id"]
    ).execute()


def run_warming_cycle(jitter: bool = True) -> dict:
    """Execute one warming cycle across all active schedules.

    Sends up to quota_for_day(current_day) - sent_today warming emails per
    inbox. Each send picks a random peer inbox from the pool. Gemini failures
    are skipped and logged; the cycle continues.

    Returns a summary dict: {schedules_processed, total_sends, errors}.
    """
    schedules = _active_schedules()
    all_inboxes = _all_active_inboxes()

    summary = {"schedules_processed": 0, "total_sends": 0, "errors": 0}

    if len(all_inboxes) < 2:
        log.warning("warming_skipped", reason="fewer than 2 active inboxes")
        return summary

    for schedule in schedules:
        inbox_uuid = schedule["inbox_id"]
        inbox = _inbox_details(inbox_uuid)
        if not inbox:
            log.warning("warming_inbox_not_found", inbox_id=inbox_uuid)
            continue

        agentmail_inbox_id = inbox.get("agentmail_inbox_id")
        if not agentmail_inbox_id:
            log.warning("warming_no_agentmail_id", inbox_id=inbox_uuid)
            continue

        quota = quota_for_day(schedule["current_day"])
        already_sent = _sent_today_count(inbox_uuid)
        remaining = quota - already_sent

        if remaining <= 0:
            log.info(
                "warming_quota_met",
                inbox_id=inbox_uuid,
                day=schedule["current_day"],
                quota=quota,
            )
            summary["schedules_processed"] += 1
            _advance_schedule(schedule)
            continue

        from_name = inbox.get("display_name") or inbox["email"].split("@")[0]
        from_email = inbox["email"]

        sends_this_cycle = 0
        all_failed = True

        for _ in range(remaining):
            if jitter and random.random() < 0.15:
                continue

            peer = _pick_peer(inbox_uuid, all_inboxes)
            if not peer:
                break

            to_name = peer.get("display_name") or peer["email"].split("@")[0]
            to_email = peer["email"]
            peer_agentmail_id = peer.get("agentmail_inbox_id")
            if not peer_agentmail_id:
                continue

            try:
                email = _generate_warming_email(from_name, from_email, to_name, to_email)
            except Exception as e:
                log.error(
                    "warming_generate_failed",
                    inbox_id=inbox_uuid,
                    error=str(e),
                )
                summary["errors"] += 1
                continue

            try:
                result = agentmail_client.send_from(
                    inbox_id=agentmail_inbox_id,
                    to=to_email,
                    subject=email.subject,
                    text=email.body,
                )
            except AgentMailError as e:
                log.error(
                    "warming_send_failed",
                    inbox_id=inbox_uuid,
                    to=to_email,
                    error=str(e),
                )
                summary["errors"] += 1
                continue

            _record_send(
                from_inbox_id=inbox_uuid,
                to_inbox_id=peer["id"],
                subject=email.subject,
                body=email.body,
                provider_thread_id=result.get("thread_id", ""),
            )
            sends_this_cycle += 1
            summary["total_sends"] += 1
            all_failed = False

        if sends_this_cycle == 0 and remaining > 0:
            if all_failed:
                log.error(
                    "warming_all_sends_failed",
                    inbox_id=inbox_uuid,
                    day=schedule["current_day"],
                    remaining=remaining,
                )
        else:
            log.info(
                "warming_cycle_done",
                inbox_id=inbox_uuid,
                day=schedule["current_day"],
                quota=quota,
                sent=sends_this_cycle,
            )

        summary["schedules_processed"] += 1
        _advance_schedule(schedule)

    return summary


def _poll_pool_replies() -> dict:
    """Check all active inboxes for replies to warming sends.

    Matches inbound thread_ids against warming_sends.provider_thread_id and
    stamps replied_at if not already set. Does not write to messages table.

    Returns {checked, matched}.
    """
    all_inboxes = _all_active_inboxes()
    since = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    summary = {"checked": 0, "matched": 0}

    for inbox in all_inboxes:
        agentmail_inbox_id = inbox.get("agentmail_inbox_id")
        if not agentmail_inbox_id:
            continue

        try:
            messages = agentmail_client.list_inbound_for_inbox(
                inbox_id=agentmail_inbox_id,
                since_dt=since,
            )
        except Exception as e:
            log.warning(
                "warming_poll_failed",
                inbox_id=inbox["id"],
                error=str(e),
            )
            continue

        summary["checked"] += len(messages)

        for m in messages:
            thread_id = m.get("thread_id")
            if not thread_id:
                continue

            send_row = (
                supabase.table("warming_sends")
                .select("id, replied_at")
                .eq("provider_thread_id", thread_id)
                .is_("replied_at", "null")
                .limit(1)
                .execute()
            )
            if not send_row.data:
                continue

            now_iso = datetime.now(timezone.utc).isoformat()
            supabase.table("warming_sends").update({"replied_at": now_iso}).eq(
                "id", send_row.data[0]["id"]
            ).execute()
            summary["matched"] += 1
            log.info("warming_reply_recorded", warming_send_id=send_row.data[0]["id"])

    return summary
