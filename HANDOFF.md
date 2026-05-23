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

### Phase 2.3 — Settings UI ⚠️ In progress — code written, NOT yet committed or pushed

**Done (files written, tsc passes, not yet committed):**

| File | Status |
|------|--------|
| `agent/src/api/routes/variants.py` | Created — GET/POST/PATCH/DELETE, JWT-auth'd |
| `agent/src/api/main.py` | Updated — variants router registered at `/api/variants` |
| `dashboard/src/lib/types.ts` | Updated — `SubjectVariant` interface added at end |
| `dashboard/src/lib/api.ts` | Updated — `listVariants`, `createVariant`, `updateVariant`, `deleteVariant` added |
| `dashboard/src/lib/hooks/useVariants.ts` | Created — SWR hook |
| `dashboard/src/components/settings/VariantsEditor.tsx` | Created — full UI component |
| `dashboard/src/app/settings/page.tsx` | Updated — `<VariantsEditor />` added below `<TestSendCard />` |

**Still needed before Phase 2.3 is complete:**
1. Commit and push all the above changes
2. Verify Railway redeploys the backend (`variants.py` route live)
3. Run the four curl commands against Railway production to verify all endpoints
4. Verify Vercel picks up the frontend changes (check the settings page renders the variants section)

---

## Phase 2.3 UI spec (for reference / verification)

The `VariantsEditor.tsx` component implements:
- Card matching `ConfigEditor` pattern: `border border-border bg-surface`, header with title + description
- `divide-y` rows, one `VariantRow` per variant
- Each `VariantRow` has:
  - Name text input
  - Subject prompt textarea (~5 rows, `resize-y`)
  - Active checkbox toggle with inline label
  - **Save** button (disabled unless row is dirty AND both fields non-empty)
  - **Delete** button — two-click arm/confirm pattern (first click turns red + shows "Confirm?", second click fires delete, blur resets)
- "+ New variant" button at bottom → inline `NewVariantRow` form (name input, prompt textarea, active checkbox, Create + Cancel buttons)
- All mutations call `mutate()` on the SWR key to refresh
- Toast notifications via `sonner`

Delete confirm copy in the handoff spec says:
> "This will delete the variant. Past sends using it stay in the database. Continue?"

The current implementation uses a two-click arm pattern instead of a dialog. If the next session wants a dialog instead, use `dashboard/src/components/ui/dialog.tsx` (it exists).

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
