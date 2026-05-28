# Hermes — Session Handoff

**Last updated:** 2026-05-27  
**Repo:** `DanteHelios/hermes` (GitHub, branch `main`)  
**Owner:** Dante Santurian / Enrique

---

## What Hermes Is

Hermes is Helios's outbound cold-email SDR agent. It:
1. **Prospects** leads (restaurants, local businesses) from Google Places by city
2. **Enriches** them (website scrape, Apollo, Firecrawl fallback) and writes a briefing
3. **Drafts** personalized cold emails using Gemini Pro — hook tier selection + subject line variant assignment
4. **Sends** via AgentMail (email) and Unipile (LinkedIn invites/DMs)
5. **Polls** for replies, classifies intent, and drafts reply emails
6. **Notifies** Dante when new inbound replies arrive (email to heliosmarketingg@gmail.com)
7. **Tracks** subject line A/B testing across variants

The dashboard (`dashboard/`) is a Next.js app. The agent backend (`agent/`) is FastAPI + Python.

---

## Infrastructure

| Service | URL | Notes |
|---------|-----|-------|
| Railway (backend) | `https://web-production-f11ee.up.railway.app` | Auto-deploys from GitHub `main` pushes |
| Vercel (frontend) | `https://hermes-phi-tawny.vercel.app` | Auto-deploys from GitHub `main` pushes (as of May 2026) |
| Supabase (DB) | `https://itoyecjtdxuouyfxsoap.supabase.co` | Same DB shared by local dev and Railway |
| GitHub | `DanteHelios/hermes` | Main branch only |

**Vercel project details:**
- Team: `helios-754baa8e` (Helios), project name: `hermes`
- `rootDirectory = dashboard` is set in Vercel project settings
- `.vercel/project.json` is gitignored — to run `vercel --prod` manually, first run `vercel link --yes --project hermes --scope helios-754baa8e` from the **repo root**
- Then: `vercel --prod --cwd /path/to/hermes` (must be run from repo root, not `dashboard/`)

**Railway:** Just push to `main`. Railway picks it up automatically.

---

## Auth

All API endpoints except `/auth/login` and `/health` require a JWT.

```bash
# Get a token (works against both local and Railway)
TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
  -d '{"password":"admin123"}' \
  https://web-production-f11ee.up.railway.app/auth/login \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Use it
curl -H "Authorization: Bearer $TOKEN" https://web-production-f11ee.up.railway.app/api/variants
```

Password: `admin123` (local and Railway use the same `.env` value).  
JWT secret and expiry are in `.env` / Railway env vars.

---

## Repo Structure

```
hermes/
├── agent/                          # FastAPI backend (Python)
│   ├── src/
│   │   ├── api/
│   │   │   ├── main.py             # App factory, router registration, CORS
│   │   │   ├── auth.py             # JWT creation/verification
│   │   │   ├── deps.py             # CurrentUser FastAPI dependency
│   │   │   └── routes/
│   │   │       ├── campaigns.py    # Campaign CRUD + tick
│   │   │       ├── chat.py         # AI chat sessions
│   │   │       ├── config.py       # Key-value config store
│   │   │       ├── inboxes.py      # Inbox CRUD + capacity (Sprint Feature 2)
│   │   │       ├── leads.py        # Lead CRUD + actions
│   │   │       ├── replies.py      # Reply drafting/approval
│   │   │       ├── run.py          # Prospect/enrich/draft/poll batch ops
│   │   │       ├── stats.py        # Dashboard stats
│   │   │       ├── test_send.py    # Test email send
│   │   │       ├── variants.py     # Subject line variants + stats
│   │   │       └── webhooks.py     # Calendly webhook
│   │   ├── clients/
│   │   │   ├── agentmail.py        # Email send/receive
│   │   │   ├── apollo.py           # Lead enrichment
│   │   │   ├── firecrawl.py        # JS-rendered site scraping fallback
│   │   │   ├── gemini.py           # Gemini Pro/Flash wrapper
│   │   │   ├── places.py           # Google Places prospecting
│   │   │   ├── supabase_client.py  # Supabase singleton
│   │   │   └── unipile.py          # LinkedIn messaging
│   │   ├── functions/
│   │   │   ├── draft.py            # Email drafting — TWO Gemini calls (body then subject)
│   │   │   ├── draft_reply.py      # Reply drafting
│   │   │   ├── enrich.py           # Lead enrichment pipeline
│   │   │   ├── poll.py             # Reply polling
│   │   │   ├── prospect.py         # Lead prospecting
│   │   │   └── send.py             # Email sending
│   │   ├── prompts/
│   │   │   ├── draft.j2            # Body-only prompt (subject removed in Phase 2.2)
│   │   │   └── subject.j2          # Subject-only prompt (new in Phase 2.2)
│   │   └── services/
│   │       └── notifications.py    # Inbound reply email notifications
│   └── sql/migrations/
│       ├── 2026_05_ab_testing.sql      # subject_variants table + messages FK
│       ├── 2026_06_variant_prompts.sql # no-op doc migration (subject_prompt already existed)
│       ├── 2026_06_inbox_capacity.sql  # inboxes table + messages.inbox_id FK
│       └── 2026_06_icp_score.sql       # icp_score, icp_score_reasons, vertical + indexes + vertical backfill
├── dashboard/                      # Next.js 15 frontend (TypeScript)
│   └── src/
│       ├── app/                    # App Router pages
│       │   ├── ab-testing/page.tsx # A/B Testing results tab
│       │   ├── approvals/page.tsx
│       │   ├── campaigns/page.tsx
│       │   ├── chat/page.tsx
│       │   ├── leads/page.tsx
│       │   ├── pipeline/page.tsx
│       │   ├── replies/page.tsx
│       │   └── settings/page.tsx
│       ├── components/
│       │   ├── ab-testing/
│       │   │   └── VariantResultsTable.tsx
│       │   ├── layout/
│       │   │   ├── Sidebar.tsx     # NAV array — add new routes here
│       │   │   └── TopBar.tsx
│       │   └── settings/
│       │       ├── ConfigEditor.tsx
│       │       ├── TestSendCard.tsx
│       │       └── VariantsEditor.tsx
│       └── lib/
│           ├── api.ts              # All API calls (apiFetch wrapper)
│           ├── auth.ts             # Zustand auth store + token helpers
│           ├── types.ts            # All TypeScript interfaces
│           └── hooks/
│               ├── useVariants.ts
│               ├── useVariantStats.ts
│               └── ... (useConfig, useLeads, useStats, etc.)
├── scripts/
│   ├── backfill_icp_scores.py      # One-off: scores all existing leads via score_lead()
│   └── ... (cron_poll, e2e_check, etc.)
├── 02_ab_testing_subject_lines.md  # Spec — "Key architectural decisions" are locked
├── hermes_sprint_spec.md           # Sprint spec (Features 1–4)
└── HANDOFF.md                      # This file
```

---

## Development

**Backend (local):**
```bash
cd agent
# Install deps
pip install -e ".[dev]"
# Run API server
uvicorn agent.src.api.main:app --reload --port 8000
```

**Frontend (local):**
```bash
cd dashboard
npm install
npm run dev   # http://localhost:3000
```

**Before pushing any dashboard change:**
```bash
cd dashboard && npm run build
```
This runs both tsc AND ESLint. The `react/no-unescaped-entities` ESLint rule blocks Vercel builds — it rejects literal `"` inside JSX text. Use `&ldquo;` / `&rdquo;` or `{'"'}` instead. Running just `tsc --noEmit` will miss this.

---

## Feature Status

### Core pipeline ✅ Shipped
- Prospect → Enrich → Draft → Approve → Send loop
- Campaign management (active/paused/completed/archived, autonomy modes)
- Reply polling, intent classification, reply drafting
- Hook tier selection (1–5 based on available intel)
- LinkedIn outreach via Unipile (invites + DMs)
- Calendly webhook → lead status update
- Test send (Settings → Test Send card)
- Reply notifications via email

### Phase 2.1 — Database schema ✅ Shipped & verified
**Commit:** `e1e7531`
- `subject_variants` table with 2 seed rows (Variant A — Direct, Variant B — Curiosity)
- `messages.subject_variant_id` UUID FK column
- `idx_messages_subject_variant` index
- Migration file: `agent/sql/migrations/2026_05_ab_testing.sql`

### Phase 2.2 — Draft logic split ✅ Shipped & verified
**Commit:** `d11a9de`
- `agent/src/prompts/draft.j2` — body prompt only (subject section removed)
- `agent/src/prompts/subject.j2` — new subject-only prompt
- `agent/src/functions/draft.py` — two sequential Gemini calls: body first, then subject
- Random 50/50 variant assignment via `random.choice()` at draft time
- `subject_variant_id` written to message row on insert
- **Body generation behavior is identical to pre-Phase 2.2 — do not touch `draft.j2` or the body call**

### Phase 2.3 — Settings UI ✅ Shipped & verified
**Commits:** `f251202`, `669e735`, `8c2f789`
- `agent/src/api/routes/variants.py` — GET/POST/PATCH/DELETE endpoints, all JWT-auth'd
- `dashboard/src/components/settings/VariantsEditor.tsx` — full CRUD UI
- `dashboard/src/app/settings/page.tsx` — `<VariantsEditor />` below `<TestSendCard />`
- Delete uses a Dialog with exact spec copy: *"This will delete the variant. Past sends using it stay in the database. Continue?"*

### Phase 2.4 — A/B Testing results tab ✅ Shipped & verified
**Commits:** `0c95a26`, `c450e80`
- `GET /api/variants/stats` — per-variant sends/replies/booked counts and rates
- `dashboard/src/app/ab-testing/page.tsx` — results page
- `dashboard/src/components/ab-testing/VariantResultsTable.tsx` — table component
- Sidebar entry: FlaskConical icon, "A/B Testing", between Replies and Leads
- Opens column always shows `—` (open tracking is a future spec)
- Footer note on statistical significance
- **`GET /stats` must stay above `PATCH /{variant_id}` and `DELETE /{variant_id}` in `variants.py`** — FastAPI matches path patterns in registration order; "stats" would be swallowed as a path param otherwise

### Sprint Feature 1 — Subject Line Prompts DB-driven ✅ Shipped & verified
**Commit:** `348db9d`

**Key finding:** `subject_prompt` column already existed in `subject_variants` from Phase 2.1. `draft.py` was already reading it from DB and injecting it into `subject.j2` via `{{ subject_prompt }}`. The system was already fully DB-driven — no schema change was needed.

**What was added:**
- `POST /api/variants/{variant_id}/preview` — renders `subject.j2` with a hardcoded fake lead (all template variables populated: company, city, google_rating, google_reviews, intel, hook_tier/text/description), fetches real sender_name/sender_title from config table, calls Gemini Pro, returns `{"preview": "..."}`. Registered above `PATCH /{variant_id}` per FastAPI ordering rules.
- `agent/sql/migrations/2026_06_variant_prompts.sql` — no-op documentation file; contains idempotent `UPDATE` seeds for both variants.
- `dashboard/src/lib/api.ts` — `previewVariant(id)` calling `POST /api/variants/{id}/preview`.
- `dashboard/src/components/settings/VariantsEditor.tsx` — Preview button with spinner; result shown in `rounded border p-2 text-sm font-mono` div below textarea; red error div on failure; textarea bumped from 5 to 6 rows.

**Gotchas:**
- `subject_prompt` (not `system_prompt`) is the existing column name — the sprint spec used `system_prompt` as a placeholder name. Do not rename.
- Route ordering in `variants.py` is now: GET `""` → POST `""` → GET `/stats` → POST `/{id}/preview` → PATCH `/{id}` → DELETE `/{id}`. Any new static-segment route must stay above the parameterized ones.
- Railway showed a brief window where `/preview` returned FastAPI's default 404 after push, then started working ~60s later (not a code bug — in-flight deployment).

---

## What's Next

### Sprint Feature 2 — Inbox Capacity Tracking ✅ Shipped & verified
**Commits:** `4413fef`, `2698c28`

**What was added:**
- `agent/sql/migrations/2026_06_inbox_capacity.sql` — `inboxes` table (email, agentmail_inbox_id, daily_send_limit, is_active), `messages.inbox_id` FK column, auto-seeded the production inbox from `agentmail_sync`, backfilled all historical `messages.inbox_id`.
- `agent/src/api/routes/inboxes.py` — GET `/capacity`, GET `""`, POST `""`, PATCH `/{inbox_id}`, DELETE `/{inbox_id}` (soft-delete). `_annotate()` adds `sent_today`, `utilization_pct`, `status` (ok/warning/blocked).
- `agent/src/functions/send.py` — `_find_inbox_uuid()` + `_check_inbox_capacity()` — raises `HTTPException(429)` when `sent_today >= daily_limit`. `inbox_id` stamped on message row at send time.
- `agent/src/functions/campaign_runner.py` — catches `HTTPException(429)` and breaks the batch.
- `agent/src/api/main.py` — registered `inboxes.router` at `/api/inboxes`.
- Dashboard: `Inbox` type, `useInboxes` hook, `InboxesEditor` component (progress bar, status badge, inline-editable limit, active toggle, add form), wired into settings page.

**Verified:** `GET /api/inboxes/capacity` returns `sent_today: 2, utilization_pct: 5.0, status: ok`. 429 test passed: PATCH limit=2 → approve lead → `{"detail":"inbox daily send limit reached"}`. Limit restored to 40.

**Gotchas:**
- PostgREST date filter: always use `datetime.now(timezone.utc).date().isoformat()` → `"2026-05-28"`. Full ISO with timezone (`+00:00`) breaks `gte` because `+` is URL-decoded as space.
- Seeded inbox: `heliosmarketingg@agentmail.to`, UUID `e602f0f3-ba89-4fae-acaf-79408f4781c4`. Update email via PATCH once you have a real sending domain.
- Route order in `inboxes.py`: GET `/capacity` must stay above PATCH/DELETE `/{inbox_id}`.

### Sprint Feature 3 — ICP Scoring + Vertical ✅ Shipped & verified
**Commits:** `808ebfc` (scoring), `f4cd0da` (Apollo diagnostics), `530b06a` (frontend), `966cc0b` (bugfix: LEAD_SUMMARY_FIELDS)

**New DB columns on `leads`:**
- `icp_score INTEGER` — 0–100 score written at the end of every enrichment run
- `icp_score_reasons JSONB` — map of reason key → points (e.g. `{"named_owner_email": 40, "healthy_review_count": 25}`)
- `vertical TEXT` — `"real_estate"`, `"restaurant"`, or `"other"`, derived from Google Places `types` array
- Migration: `agent/sql/migrations/2026_06_icp_score.sql` — adds columns + indexes + SQL backfill of `vertical` for all existing leads

**Scoring logic — `agent/src/functions/enrich.py`:**
- `score_lead(lead: dict) -> tuple[int, dict]` added just above `enrich()`. Called as step 12 (final step) of the enrich pipeline using local variables (`verified_owner_email`, `verified_general_email`, `lead["google_reviews"]`, `lead["website"]`, `owner_name`) so it never re-fetches the row.
- Weights: named owner email (+40), named non-generic email (+25), generic email (+10), healthy reviews 50–500 (+25), >500 reviews (+15), 10–49 reviews (+5), has website (+10), owner name known (+10). Cap: 100.
- `owner_email` and `general_email` live in `intel_json`, NOT as top-level columns. The score_lead call passes them explicitly from local vars — do not pass the raw lead row.

**Vertical classifier (SQL, runs once in migration):**
- `real_estate_agency` in `intel_json->'types'` → `"real_estate"`
- Any type containing `restaurant` or `food` → `"restaurant"`
- Else → `"other"`
- New leads get `vertical` set only if added by a future enrichment step that writes it, or via a follow-up migration.

**Backfill script:** `scripts/backfill_icp_scores.py` — scores all existing leads using the same `score_lead()` import. Run from repo root: `.venv/bin/python scripts/backfill_icp_scores.py`. Results: 21 leads ≥70, 17 leads 40–69, 15 leads <40.

**Apollo investigation findings (Part B):**
- `/v1/people/match` (contact enrichment) — **paywalled on free plan, returns HTTP 403**. Not a code bug. Contact title/role data unavailable without paid plan.
- `/v1/organizations/enrich` (org data) — **works on free plan**, returns headcount/founded_year/description/industry/phone. Confirmed live against 3 real domains.
- Zero Apollo data on all 53 existing leads because `APOLLO_API_KEY` was added to Railway after all leads were already enriched. New leads will get org data. Backfill deferred until something downstream consumes it.
- Diagnostic logging added to `agent/src/clients/apollo.py`: logs `apollo_call_start`, `apollo_response`, `apollo_no_match`, `apollo_contact_no_person`, `apollo_org_no_data`, and disabled-skip paths.

**Frontend (Part C) — `dashboard/src/`:**
- `lib/types.ts` — `Lead` interface extended with `icp_score: number | null`, `icp_score_reasons: Record<string, number> | null`, `vertical: "real_estate" | "restaurant" | "other" | null`
- `components/leads/LeadsTable.tsx` — new `ICP` column (score + color dot: green ≥70, yellow 40–69, red <40, grey null) with hover tooltip showing reasons breakdown; new `Vertical` column (small border badge); default sort changed to `icp_score DESC NULLS LAST`; `SortField` type extended with `"icp_score"`
- `components/leads/LeadFilters.tsx` — `icpOnly: boolean` added to `LeadFiltersState`; ICP ≥ 40 toggle chip (styled button, default **off**)
- `app/leads/page.tsx` — `icpOnly: false` in initial state; filter logic gates on `lead.icp_score >= 40`; active filter count includes `icpOnly`

**Gotcha:** See LEAD_SUMMARY_FIELDS in Known Quirks below — this bug bit Feature 3 on first deploy.

---

### Phase 2.5 — End-to-end verification (NOT done)
From the spec (`02_ab_testing_subject_lines.md` section "Phase 2.5"):

1. Run a draft batch → check DB for ~50/50 split:
   ```sql
   SELECT subject_variant_id, COUNT(*)
   FROM messages
   WHERE direction = 'outbound'
     AND created_at > now() - interval '1 hour'
   GROUP BY subject_variant_id;
   ```
2. Confirm Settings page shows both variants and Save works
3. Toggle one variant inactive → run another draft batch → confirm all new drafts use the remaining active variant
4. Confirm A/B Testing tab loads and shows real numbers
5. Confirm Test Send still works normally (it picks a variant just like real sends)

These are behavioral tests requiring the pipeline to actually run — can't be verified by curl alone.

### Sprint Feature 4 — Email Warming (not started)
Full spec in `hermes_sprint_spec.md` § 4. ~2 days effort. Key pieces:
- `warming_schedule` + `warming_sends` tables
- `agent/src/services/warming.py` — ramp schedule (5→10→20→35→40 sends/day over 5 weeks)
- `agent/src/services/warming_cron.py` — daily cron at 08:00 UTC
- `agent/src/prompts/warming.j2` — Gemini Flash generates mundane colleague emails
- `agent/src/api/routes/warming.py` — GET/POST/PATCH/DELETE `/api/warming`
- `dashboard/src/app/warming/page.tsx` — new page, Flame icon in sidebar
- Warming sends must NOT count against `inboxes.daily_send_limit` (tag `messages.is_warming = true` and exclude from `sent_today` query)
- Reply poller must detect warming replies (check `X-Warming` header or sender in inbox pool) and not trigger notification system

### Future specs (not started)
- Open rate tracking (separate spec)
- Phase 2.5 end-to-end
- Anything else Dante adds

---

## Critical Constraints

- **Do not touch `draft.j2` or the body generation call in `draft.py`.** Body prompt behavior must stay identical to Phase 2.2 state forever.
- **Subject variant assignment is 50/50 random at draft time.** Do not change the `random.choice()` logic.
- **JWT auth is required on all `/api/variants/*` endpoints.** Use the `CurrentUser` FastAPI dependency.
- **Variants are global** (not per-campaign). The spec explicitly locked this.
- **No auto-promotion of winning variants.** Manual only — Dante reviews numbers and decides.

---

## Known Quirks & Gotchas

**ESLint `react/no-unescaped-entities`:** Any literal `"` inside JSX text content (not attributes) will fail the Vercel build. `tsc --noEmit` does NOT catch this — only `npm run build` does. Always run the full build before pushing dashboard changes.

**FastAPI route ordering:** In `variants.py`, `GET /stats` must be registered before `PATCH /{variant_id}` / `DELETE /{variant_id}`. Starlette matches path patterns in order; `/stats` would be treated as `/{variant_id}` with `variant_id="stats"` if the parameterized routes come first, returning 405 instead of routing correctly.

**Vercel deploy from CLI:** The `.vercel/project.json` is gitignored. If it's not on disk, run `vercel link --yes --project hermes --scope helios-754baa8e` from the **repo root** before `vercel --prod`. Always run `vercel --prod` from repo root (or with `--cwd /path/to/hermes`), never from inside `dashboard/` — the Vercel project has `rootDirectory = dashboard` set, so running from inside dashboard doubles the path.

**Supabase `sends` counts:** All existing messages sent before Phase 2.2 have `subject_variant_id = NULL`. The A/B stats endpoint filters those out. Variant counts will be 0 until new drafts are generated after Phase 2.2 was deployed.

**`LEAD_SUMMARY_FIELDS` in `leads.py`:** `GET /api/leads` selects an explicit column string (`LEAD_SUMMARY_FIELDS` at the top of `agent/src/api/routes/leads.py`), not `select("*")`. Whenever you add a new column to the `leads` table that the frontend needs in the list view, you must also add it to this string — PostgREST silently drops fields not in the select list. `GET /api/leads/{id}` uses `select("*")` so detail views are unaffected. Feature 3 shipped with this bug on first deploy (ICP and Vertical showed as null/— until `966cc0b` fixed it).

**Apollo plan restriction:** `/v1/people/match` (contact lookup by email) returns HTTP 403 on Apollo's free plan with `{"error_code": "API_INACCESSIBLE"}`. `/v1/organizations/enrich` works on the free plan. All existing leads have zero Apollo data because `APOLLO_API_KEY` was added to Railway after enrichment had already run. New enrichment runs will populate `intel_json["apollo"]["org"]` for leads with a resolvable domain. Org-data backfill deferred.

**Railway `$PORT`:** Railway injects `$PORT` at runtime. `run_api.py` and `railway.toml` respect this — don't hardcode port 8000 in any new Railway-specific config.

**CORS:** `main.py` allows `localhost:3000`, `hermes-phi-tawny.vercel.app`, and regex `https://hermes.*\.vercel\.app`. If you add a new Vercel domain, update the regex or add an explicit origin.

---

## API Quick Reference

All endpoints require `Authorization: Bearer <token>` except `/auth/login` and `/health`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Get JWT (`{"password": "..."}`) |
| GET | `/health` | Health check |
| GET | `/api/variants` | List all subject variants |
| POST | `/api/variants` | Create variant |
| GET | `/api/variants/stats` | Per-variant A/B stats |
| POST | `/api/variants/{id}/preview` | Preview subject line via Gemini (fake lead) |
| PATCH | `/api/variants/{id}` | Update variant fields |
| DELETE | `/api/variants/{id}` | Delete variant (204) |
| GET | `/api/stats` | Dashboard stats |
| GET | `/api/leads` | List leads (status filter, limit) — includes `icp_score`, `icp_score_reasons`, `vertical` |
| POST | `/api/run/draft-batch` | Run draft batch |
| POST | `/api/run/enrich-batch` | Run enrich batch |
| POST | `/api/run/poll-replies` | Poll for new replies |
| POST | `/api/test-send` | Send test email |
| GET | `/api/config` | Get config key-value store |
| POST | `/api/config` | Set config value |
| GET | `/api/inboxes/capacity` | Inbox utilization (same as GET /api/inboxes) |
| GET | `/api/inboxes` | List inboxes with sent_today/utilization/status |
| POST | `/api/inboxes` | Register inbox |
| PATCH | `/api/inboxes/{id}` | Update email, limit, or is_active |
| DELETE | `/api/inboxes/{id}` | Soft-delete inbox (204) |
