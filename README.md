# Helios SDR Agent

AI-powered sales development agent that discovers real estate brokerages via Google Places, scrapes their websites for intelligence, and drafts personalized cold emails using a hook-tier system powered by Gemini. Phase 1 is a CLI-only pipeline that prospects, enriches, and drafts — no sending, no dashboard, no scheduling.

## Phase 1 Scope

**Built:**
- Google Places prospecting (searchText API)
- Website scraping + subpage crawling (requests + BeautifulSoup)
- Enrichment extraction via Gemini 2.5 Flash (structured output)
- Cold email drafting via Gemini 2.5 Pro with 5-tier hook system
- Supabase (Postgres) storage for leads, messages, and config
- Rich terminal output with draft panels and summary tables
- Redraft loop for iterating on individual leads

**Not built (Phase 2):**
- Email send/receive (Phase 2a adds AgentMail integration)
- FastAPI server / Next.js dashboard
- Cron scheduling / deployment
- Reply handling / intent classification
- Calendly integration / auth

## Setup

1. **Supabase**: Create a project at [supabase.com](https://supabase.com). Copy the project URL and service role key (Settings > API).

2. **Gemini API key**: Get one from [aistudio.google.com](https://aistudio.google.com).

3. **Google Places API key**: Create a key in the [GCP Console](https://console.cloud.google.com). Enable the **Places API (New)**.

4. **Environment variables**:
   ```bash
   cp .env.example .env
   # Fill in all keys in .env
   ```

5. **Database schema**: Open the Supabase SQL Editor and run:
   - `agent/sql/schema.sql` (creates tables, indexes, triggers)
   - `agent/sql/seed.sql` (inserts default config)

6. **Install dependencies**:
   ```bash
   make install
   ```

7. **Run the test**:
   ```bash
   make test-single-lead CITY=Miami
   ```

## What Success Looks Like

The test harness discovers 5 brokerages in your target city, scrapes their websites, extracts structured intel via Gemini Flash, and drafts personalized cold emails via Gemini Pro. Output includes:

- Rich-formatted email panels showing subject, body, hook tier, and rationale
- A summary table with each lead's final status, hook tier quality, and email availability

Some leads may end up `dead` (no website, fetch failed, no email found). That's expected — partial success is normal.

## Iteration

To regenerate the draft for a specific lead:

```bash
make redraft LEAD_ID=<uuid>
```

This enters a loop: draft, display, confirm. Say `y` to redraft or `n` to accept.

## Reset

To clear all leads and messages (preserves config):

```bash
make reset-db
```

## Phase 2a — AgentMail + API

Phase 2a adds email send/receive via [AgentMail](https://agentmail.to), a FastAPI backend, and JWT auth. AgentMail is an API-first email provider built for AI agents — no Google Workspace, no service accounts, no DWD. The inbox is auto-provisioned on first call.

### Setup

1. **Sign up**: Create an account at [agentmail.to](https://agentmail.to) and generate an API key from the console.

2. **Add env vars** to `.env`:
   ```
   AGENTMAIL_API_KEY=am_xxx
   AGENTMAIL_INBOX_USERNAME=outreach
   AGENTMAIL_INBOX_DOMAIN=          # leave blank for default @agentmail.to
   DASHBOARD_PASSWORD=your-password
   JWT_SECRET=your-32-char-secret
   ```

3. **(Optional, paid plan)** Configure a custom domain in the AgentMail console and set `AGENTMAIL_INBOX_DOMAIN` to your verified domain.

4. **Update schema**: Re-run `agent/sql/schema.sql` in the Supabase SQL Editor (idempotent — migrates `gmail_*` columns to `provider_*` and creates `agentmail_sync`).

5. **Install deps**:
   ```bash
   make install
   ```

6. **Start the API**:
   ```bash
   make api
   ```
   The first call to any send/poll function auto-creates the inbox.

### Running

```bash
make api               # starts FastAPI on :8000
make daily-run         # manually trigger prospect/enrich/draft
make poll-replies      # manually check AgentMail for replies
make send MESSAGE_ID=xxx  # send a single drafted message
```

### Verification Workflow (curl)

```bash
# 1. Login and get JWT
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"your-password"}' | jq -r .token)

# 2. Check stats
curl http://localhost:8000/api/stats \
  -H "Authorization: Bearer $TOKEN"

# 3. List drafted leads
curl "http://localhost:8000/api/leads?status=drafted" \
  -H "Authorization: Bearer $TOKEN"

# 4. Test-send a draft to your own inbox
curl -X POST http://localhost:8000/api/test-send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"lead_id":"<uuid>","to":"your-email@gmail.com"}'

# 5. Approve and actually send to the broker
curl -X POST http://localhost:8000/api/leads/<uuid>/approve \
  -H "Authorization: Bearer $TOKEN"
```

## Troubleshooting

_To be filled after first run._
