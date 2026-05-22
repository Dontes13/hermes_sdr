"""Cron-invoked script to poll replies and fire notifications.

Runs every 5 minutes via Railway cron. Calls the same code path as
the manual `make poll-replies` command.
"""
from agent.src.config import settings  # noqa: F401 — loads .env before other imports

import structlog

from agent.src.functions.poll import poll_replies
from agent.src.functions.poll_linkedin import poll_linkedin

log = structlog.get_logger(__name__)

if __name__ == "__main__":
    email_summary = poll_replies()
    li_summary = poll_linkedin()
    log.info("cron_poll_complete", email=email_summary, linkedin=li_summary)
