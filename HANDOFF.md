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
│       └── 2026_05_ab_testing.sql  # subject_variants table + messages FK
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
├── 02_ab_testing_subject_lines.md  # Spec — "Key architectural decisions" are locked
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
| GET | `/api/leads` | List leads (status filter, limit) |
| POST | `/api/run/draft-batch` | Run draft batch |
| POST | `/api/run/enrich-batch` | Run enrich batch |
| POST | `/api/run/poll-replies` | Poll for new replies |
| POST | `/api/test-send` | Send test email |
| GET | `/api/config` | Get config key-value store |
| POST | `/api/config` | Set config value |
