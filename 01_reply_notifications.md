# Hermes — Reply Notifications

**Owner:** Dante / Enrique
**Status:** Spec ready for implementation
**Estimated work:** 2–4 hours
**Do this BEFORE the A/B testing spec.** This is smaller and de-risks the bigger one.

---

## Goal

When a new inbound reply lands in Hermes (detected by `runPollReplies`), send a notification email to `heliosmarketingg@gmail.com` so the Helios team knows to log in and respond.

**Non-goals (do NOT build any of this):**
- Auto-reply via AI (humans handle all replies; AI drafts already exist and stay as suggestions)
- Slack / SMS / push notifications (email only for v1)
- Per-campaign routing (all notifications go to the one address)
- Custom templates per intent
- Notification preferences UI

Keep it small. One job: when reply detected → send email to one address.

---

## Architecture decisions (already made — don't re-litigate)

1. **Channel:** Email (not Slack). Sent via the same AgentMail integration the rest of the app uses — no new provider.
2. **Recipient:** Hardcoded `heliosmarketingg@gmail.com`. Stored as a settings key in Supabase (`notify_email`) so it can be changed without redeploy, but it's a single value, not a list.
3. **Trigger:** Scheduled poll via Railway cron every 5 minutes. The existing `runPollReplies` endpoint already does the detection — we just need to (a) call it on a schedule and (b) fire notifications for any newly detected replies.
4. **No real-time webhooks.** We're not adding AgentMail webhook integration for v1, even if AgentMail supports it. Polling every 5 min is fine — a 5-min delay on a reply notification is acceptable.

---

## Implementation plan

### Phase 1.1 — Database migration

Add a column to track which inbound messages have already triggered a notification, so we don't double-notify if the cron runs twice in a row.

**File:** `agent/sql/migrations/2026_05_reply_notifications.sql` (create new)

```sql
-- Track whether a notification has been sent for an inbound reply
ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS notification_sent_at TIMESTAMPTZ;

-- Add the notification recipient to config (idempotent — only insert if missing)
INSERT INTO config (key, value)
VALUES ('notify_email', 'heliosmarketingg@gmail.com')
ON CONFLICT (key) DO NOTHING;
```

**Run instruction for Dante:** After Claude Code commits this file, Dante runs it manually in the Supabase SQL Editor. Tell Dante explicitly: "Open Supabase → SQL Editor → paste the contents of `agent/sql/migrations/2026_05_reply_notifications.sql` → Run."

### Phase 1.2 — Notification sender

**File:** `agent/src/services/notifications.py` (create new)

Create a function `send_reply_notification(message: Message, lead: Lead) -> bool` that:

1. Reads `notify_email` from the `config` table via Supabase
2. Composes an email with:
   - **Subject:** `New reply from {lead.company} — needs response`
   - **Body:** plaintext, something like:
     ```
     Hi team,

     A new reply just came in from {lead.company} and needs a response.

     From: {message.from_email or lead.email}
     Company: {lead.company}
     Subject: {message.subject or '(no subject)'}

     First lines of their reply:
     {first 500 chars of message.body, with "..." if truncated}

     Reply intent (AI-classified): {message.reply_intent or 'not classified'}

     Open the dashboard to view the full thread and respond:
     https://hermes-phi-tawny.vercel.app/replies

     — Hermes
     ```
3. Sends via the existing AgentMail client (do not add a new send path — reuse the function the rest of the app uses to send outbound mail).
4. On success, returns `True`. On failure, logs the error with `structlog` and returns `False` — never raises to the caller, because a failed notification should not break the polling loop.

**Important constraints:**
- Reuse the existing AgentMail send function, do not reimplement it.
- The `from` address on the notification should be the same sender identity Hermes uses for outbound — do not introduce a second sender.
- Plaintext only for v1. No HTML.

### Phase 1.3 — Wire it into the poll

**File:** `agent/src/api/routes/pipeline.py` (or wherever `runPollReplies` is defined — find it via `grep -r "poll_replies" agent/src`)

The existing `poll_replies` endpoint already detects new inbound messages and writes them to the `messages` table. We need to:

1. After each new inbound message is inserted, check if `notification_sent_at` is null
2. Call `send_reply_notification(message, lead)`
3. If it returns `True`, update `messages.notification_sent_at = now()` for that row

Do NOT change the existing detection logic. Add notification logic in a `try/except` block around the new behavior so notification failures cannot break reply detection.

### Phase 1.4 — Scheduled polling

Railway supports cron jobs natively. Add a new service to the existing Railway project:

**File:** `scripts/cron_poll.py` (create new)

```python
"""Cron-invoked script to poll replies and fire notifications.

Runs every 5 minutes via Railway cron. Calls the same code path as
the manual `make poll-replies` command.
"""
import asyncio
from agent.src.services.poll_replies import run_poll_replies

if __name__ == "__main__":
    asyncio.run(run_poll_replies())
```

**Update `railway.toml`** to add a cron service alongside the existing `web` service:

```toml
[[services]]
name = "poll-cron"
buildCommand = "pip install -e ."
startCommand = "python scripts/cron_poll.py"
cronSchedule = "*/5 * * * *"
```

(Verify the exact railway.toml syntax for cron in Railway's docs — the above is the standard format but Railway may want it under a different key. If `cronSchedule` doesn't work, check Railway's "cron jobs" docs.)

**Run instruction for Dante:** After this is deployed, verify in Railway dashboard that there are now TWO services: `web` (the API) and `poll-cron` (the scheduled job). The cron service should run every 5 minutes and show successful runs in its logs.

---

## Verification checklist

After implementation, Claude Code must verify all of these before reporting done:

- [ ] Migration file exists at `agent/sql/migrations/2026_05_reply_notifications.sql`
- [ ] `notifications.py` exists and imports cleanly (`python -c "from agent.src.services.notifications import send_reply_notification"`)
- [ ] `runPollReplies` calls `send_reply_notification` for new inbounds
- [ ] `scripts/cron_poll.py` exists and runs without error locally (test: `python scripts/cron_poll.py` — should complete without crashing even if no new replies)
- [ ] `railway.toml` has a second service entry for the cron
- [ ] Code committed and pushed to `DanteHelios/hermes` on `main`

Then tell Dante to:

1. Run the SQL migration in Supabase
2. Verify Railway picked up the new cron service (look for it in the project view)
3. Wait for one cron execution (≤5 min) and confirm it ran cleanly in Railway logs
4. **Test end-to-end:** send a reply from a personal email to one of the AgentMail addresses Hermes sent to, then wait up to 5 minutes — `heliosmarketingg@gmail.com` should receive a notification

---

## What "done" looks like

Dante sends a reply email to one of Hermes's sent leads, and within 5 minutes a notification email lands at `heliosmarketingg@gmail.com` saying "New reply from {company} — needs response" with a working link to the Replies tab. The dashboard's existing reply flow (with AI drafts and Edit button) continues to work unchanged.

---

## Out of scope for this spec — do NOT touch

- The AI reply drafting logic. It stays.
- The dashboard's Replies UI. It stays.
- Any other notification channels.
- Per-campaign routing.
- Open rate tracking (separate future project).
- A/B testing (separate spec — do that AFTER this one ships).
