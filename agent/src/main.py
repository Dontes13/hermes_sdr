"""CLI entry point for make targets.

Usage:
    python -m agent.src.main daily-run
    python -m agent.src.main poll-replies
    python -m agent.src.main send --message-id <uuid>
"""

import argparse
import sys

# Load .env before any other imports
from agent.src.config import settings  # noqa: F401

import structlog

from agent.src.clients.supabase_client import supabase
from agent.src.functions.campaign_runner import run_all_active_campaigns
from agent.src.functions.draft import draft
from agent.src.functions.enrich import enrich
from agent.src.functions.poll import poll_replies
from agent.src.functions.poll_linkedin import poll_linkedin
from agent.src.functions.prospect import prospect
from agent.src.functions.send import send

log = structlog.get_logger(__name__)


def cmd_daily_run(args: argparse.Namespace) -> None:
    """Run prospect/enrich/draft pipeline for all configured cities."""
    # Get target cities from config table
    config_resp = (
        supabase.table("config")
        .select("value")
        .eq("key", "target_cities")
        .execute()
    )
    if not config_resp.data:
        log.error("daily_run_no_cities", msg="Set 'target_cities' in config table")
        sys.exit(1)

    cities_raw = config_resp.data[0]["value"]
    cities = [c.strip() for c in cities_raw.split(",") if c.strip()]
    log.info("daily_run_start", cities=cities)

    # 1. Prospect
    all_new_ids: list[str] = []
    for city in cities:
        ids = prospect(city, max_leads=5)
        all_new_ids.extend(ids)
        log.info("daily_run_prospected", city=city, count=len(ids))

    # 2. Enrich all status='new' leads (cap 20)
    new_leads = (
        supabase.table("leads")
        .select("id")
        .eq("status", "new")
        .limit(20)
        .execute()
    )
    enriched = 0
    for row in new_leads.data:
        try:
            enrich(row["id"])
            enriched += 1
        except Exception as e:
            log.warning("daily_run_enrich_error", lead_id=row["id"], error=str(e))
    log.info("daily_run_enriched", count=enriched)

    # 3. Draft all status='enriched' leads (cap 15)
    enriched_leads = (
        supabase.table("leads")
        .select("id")
        .eq("status", "enriched")
        .limit(15)
        .execute()
    )
    drafted = 0
    for row in enriched_leads.data:
        try:
            draft(row["id"])
            drafted += 1
        except Exception as e:
            log.warning("daily_run_draft_error", lead_id=row["id"], error=str(e))
    log.info("daily_run_drafted", count=drafted)

    log.info(
        "daily_run_complete",
        prospected=len(all_new_ids),
        enriched=enriched,
        drafted=drafted,
    )


def cmd_poll_replies(args: argparse.Namespace) -> None:
    """Poll AgentMail (email) and Unipile (LinkedIn) for new inbound.

    LinkedIn polling is a no-op when Unipile env vars are unset, so this
    command stays safe to run on email-only deployments.
    """
    email_summary = poll_replies()
    li_summary = poll_linkedin()
    print({"email": email_summary, "linkedin": li_summary})


def cmd_send(args: argparse.Namespace) -> None:
    """Send a single message by ID."""
    response = send(args.message_id)
    print(f"Sent. Provider message ID: {response['message_id']}")


def cmd_run_campaigns(args: argparse.Namespace) -> None:
    """Advance every active campaign by one tick. Intended for cron."""
    results = run_all_active_campaigns()
    if not results:
        log.info("run_campaigns_no_active")
        print("No active campaigns.")
        return
    for summary in results:
        print(summary)


def main() -> None:
    parser = argparse.ArgumentParser(description="Helios SDR CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("daily-run", help="Run full prospect/enrich/draft pipeline")
    subparsers.add_parser("poll-replies", help="Poll AgentMail for new replies")
    subparsers.add_parser(
        "run-campaigns", help="Tick every active campaign (cron-friendly)"
    )

    send_parser = subparsers.add_parser("send", help="Send a single message")
    send_parser.add_argument("--message-id", required=True, help="Message UUID to send")

    args = parser.parse_args()

    commands = {
        "daily-run": cmd_daily_run,
        "poll-replies": cmd_poll_replies,
        "run-campaigns": cmd_run_campaigns,
        "send": cmd_send,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
