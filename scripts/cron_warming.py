"""Cron-invoked script to run one email warming cycle.

NOT added to railway.toml — must be enabled manually once the inbox pool
has at least 2 active inboxes. Runs daily (or on whatever schedule you set).
"""
from agent.src.config import settings  # noqa: F401 — loads .env before other imports

import structlog

from agent.src.services.warming import _poll_pool_replies, run_warming_cycle

log = structlog.get_logger(__name__)

if __name__ == "__main__":
    send_summary = run_warming_cycle(jitter=True)
    reply_summary = _poll_pool_replies()
    log.info("cron_warming_complete", sends=send_summary, replies=reply_summary)
