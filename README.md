# Helios SDR Agent

An AI-powered sales development agent that finds real estate brokerages, researches them automatically, and drafts personalized cold outreach emails — end to end, from prospecting to sending.

## What it does

Give it a city, and the agent will:

1. **Discover** real estate brokerages in that area using the Google Places API
2. **Research** each one by crawling their website and extracting key intelligence with Gemini
3. **Draft** a personalized cold email using a 5-tier hook system, so the pitch actually references something specific about the business
4. **Send and track** outreach via AgentMail, with reply polling and a JWT-secured API for approvals

It's built to remove the manual grind of SDR work — no spreadsheets, no copy-pasting company details, no generic templates.

## Tech stack

- **Python** — core agent pipeline (prospecting, scraping, enrichment, drafting)
- **Google Places API** — brokerage discovery
- **BeautifulSoup + requests** — website scraping and subpage crawling
- **Gemini 2.5 Flash** — structured data extraction from scraped content
- **Gemini 2.5 Pro** — cold email generation with hook-tier reasoning
- **Supabase (Postgres)** — storage for leads, messages, and config
- **FastAPI** — backend API for sending, polling, and approvals
- **AgentMail** — API-first email provider (send/receive, auto-provisioned inbox)
- **Rich** — terminal output for draft review and summary tables

## Setup

1. **Supabase** — create a project at [supabase.com](https://supabase.com) and copy the project URL and service role key from Settings → API.

2. **Gemini API key** — get one from [aistudio.google.com](https://aistudio.google.com).

3. **Google Places API key** — create a key in the [GCP Console](https://console.cloud.google.com) and enable the **Places API (New)**.

4. **AgentMail API key** — sign up at [agentmail.to](https://agentmail.to) and generate a key from the console.

5. **Environment variables**:
   ```bash
   cp .env.example .env
   ```
   Fill in:
   ```
   GOOGLE_PLACES_API_KEY=
   GEMINI_API_KEY=
   SUPABASE_URL=
   SUPABASE_SERVICE_ROLE_KEY=
   AGENTMAIL_API_KEY=am_xxx
   AGENTMAIL_INBOX_USERNAME=outreach
   AGENTMAIL_INBOX_DOMAIN=          # leave blank for default @agentmail.to
   DASHBOARD_PASSWORD=your-password
   JWT_SECRET=your-32-char-secret
   ```

6. **Database schema** — in the Supabase SQL Editor, run:
   - `agent/sql/schema.sql`
   - `agent/sql/seed.sql`

7. **Install dependencies**:
   ```bash
   make install
   ```

## Running it

```bash
make test-single-lead CITY=Miami   # discover, enrich, and draft for a test city
make api                            # start the FastAPI server on :8000
make daily-run                      # manually trigger the full prospect/enrich/draft cycle
make poll-replies                   # check AgentMail for new replies
make send MESSAGE_ID=xxx            # send a single drafted message
```

To regenerate a draft you're not happy with:

```bash
make redraft LEAD_ID=<uuid>
```
This enters a draft → review → accept/redraft loop.

To wipe leads and messages while keeping your config:

```bash
make reset-db
```

## API quickstart

```bash
# Login and get a JWT
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"your-password"}' | jq -r .token)

# Check stats
curl http://localhost:8000/api/stats \
  -H "Authorization: Bearer $TOKEN"

# List drafted leads
curl "http://localhost:8000/api/leads?status=drafted" \
  -H "Authorization: Bearer $TOKEN"

# Test-send a draft to your own inbox
curl -X POST http://localhost:8000/api/test-send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"lead_id":"<uuid>","to":"your-email@gmail.com"}'

# Approve and send to the broker
curl -X POST http://localhost:8000/api/leads/<uuid>/approve \
  -H "Authorization: Bearer $TOKEN"
```

## What success looks like

A run against a target city surfaces a handful of brokerages, scrapes their sites, extracts structured intel, and produces personalized draft emails — shown in the terminal as formatted panels with subject, body, hook tier, and rationale, followed by a summary table. Some leads will end up `dead` (no website, failed fetch, no email found) — that's expected; partial success across a batch is normal.

## Troubleshooting

_To be filled in as issues come up._
