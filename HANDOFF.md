# Hermes A/B Testing — Session Handoff

## Spec file
`hermes/02_ab_testing_subject_lines.md`
Read this before continuing. The "Key architectural decisions" and "Non-goals" sections are locked.

---

## Phase status

### Phase 2.1 — Database schema ✅ Shipped & verified
- Migration: `agent/sql/migrations/2026_05_ab_testing.sql`
- `subject_variants` table created with 2 seed rows (Variant A — Direct, Variant B — Curiosity)
- `messages.subject_variant_id` UUID FK column added
- `idx_messages_subject_variant` index confirmed in Supabase

### Phase 2.2 — Draft logic split ✅ Shipped & verified
- `agent/src/prompts/draft.j2` — body prompt only (subject section removed, one-liner awareness added)
- `agent/src/prompts/subject.j2` — new, subject-only prompt template
- `agent/src/functions/draft.py` — split into two sequential Gemini calls: body first, then subject
- Random 50/50 variant assignment at draft time via `random.choice()`
- `subject_variant_id` stored on message row
- Body generation is behaviorally identical to before Phase 2.2

### Phase 2.3 — Settings UI ✅ Shipped & verified

Commits:
- `f251202` — initial VariantsEditor implementation
- `669e735` — delete confirm replaced with Dialog (spec copy)
- `8c2f789` — fix ESLint `react/no-unescaped-entities` (was blocking Vercel build)

All four `/api/variants` endpoints verified via curl against Railway. Delete test variant confirmed removed. Bundle confirmed on `hermes-phi-tawny.vercel.app`.

**Deployed files:**

| File | Status |
|------|--------|
| `agent/src/api/routes/variants.py` | GET/POST/PATCH/DELETE, JWT-auth'd |
| `agent/src/api/main.py` | variants router at `/api/variants` |
| `dashboard/src/lib/types.ts` | `SubjectVariant` interface |
| `dashboard/src/lib/api.ts` | `listVariants`, `createVariant`, `updateVariant`, `deleteVariant` |
| `dashboard/src/lib/hooks/useVariants.ts` | SWR hook |
| `dashboard/src/components/settings/VariantsEditor.tsx` | Full UI — Dialog confirm with spec copy |
| `dashboard/src/app/settings/page.tsx` | `<VariantsEditor />` below `<TestSendCard />` |

**Delete confirm dialog copy (verified in prod bundle):**
> "This will delete the variant. Past sends using it stay in the database. Continue?"

---

## Vercel deploy process (manual — GitHub auto-deploy is not wired)

The Vercel project is `hermes` under team `helios-754baa8e`. GitHub pushes do NOT auto-deploy. For each phase, after pushing to GitHub, deploy manually:

```bash
# From repo root (~/Helios/hermes), not dashboard/
vercel --prod --cwd /path/to/hermes
# Or cd to repo root first, then:
cd ~/Helios/hermes && vercel --prod
```

The `.vercel/project.json` at repo root is already linked to `helios-754baa8e/hermes`. Vercel project settings have `rootDirectory = dashboard`.

---

## Phase 2.4 — A/B Testing results tab (NOT started)

After Phase 2.3 is verified in prod:
- New sidebar nav entry: "A/B Testing"
- New route: `dashboard/src/app/ab-testing/page.tsx`
- New component: `VariantResultsTable.tsx`
- New backend endpoint: `GET /api/variants/stats`
- Stats should show per-variant: send count, open rate (if available), reply rate, book rate

---

## Critical constraints
- **Body prompt behavior** must stay identical to Phase 2.2 state — do not touch `draft.j2` or the body generation call in `draft.py`
- **JWT auth** is required on all `/api/variants/*` endpoints — already done via `CurrentUser` dep
- **Subject variant assignment** is 50/50 random at draft time — do not change the assignment logic

---

## Infrastructure reminders
- Railway backend: `https://web-production-f11ee.up.railway.app`
- Vercel frontend: `https://hermes-phi-tawny.vercel.app`
- Supabase: shared between local and Railway (same DB)
- `NEXT_PUBLIC_API_URL` must be set on Vercel to the Railway URL (Dante confirmed this was done)
- CORS: `main.py` allows `localhost:3000`, `hermes-phi-tawny.vercel.app`, and regex `https://hermes.*\.vercel\.app`
