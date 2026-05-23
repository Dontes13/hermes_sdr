# Hermes — Subject Line A/B Testing

**Owner:** Dante / Enrique
**Status:** Spec ready for implementation
**Estimated work:** 1–2 days
**Do this AFTER the Reply Notifications spec ships and is verified working in prod.**

---

## Goal

A/B test **subject lines** against each other to find which subject line variants drive higher reply rates. Everything else — email body, hook, sender, timing — stays identical. We are testing **one variable only**: the subject line generation prompt.

A "variant" in this spec is a **subject line generation prompt**, not a whole email prompt. The body prompt stays the same across all variants.

---

## Non-goals (do NOT build)

- A/B testing of email body, hook tier strategy, sender identity, or anything other than subject lines
- More than 2 simultaneous variants in v1 (data model supports N, but UI/logic defaults to 2)
- Multi-armed bandit / automatic winner selection / Bayesian stats
- Auto-promote of winning variants (you'll do this manually based on dashboard data)
- Per-campaign variant assignment (variants are global)
- Cross-variant content mixing (each lead gets exactly one variant, fixed for life)

If something feels like scope creep, it is. Push back to spec scope.

---

## Key architectural decisions (locked in — do not re-litigate)

1. **What's varied:** Subject line generation prompt only. Body prompt is constant.
2. **Assignment:** 50/50 random per lead, at draft time. Once assigned, a lead's variant never changes.
3. **Variant count:** 2 active variants at a time in v1. Data model supports N, but the UI shows 2 slots.
4. **Variant management:** Created and edited via a new **Prompt Variants** section in the dashboard Settings page. Each variant has: name, subject prompt text, active flag.
5. **Results UI:** New top-level **A/B Testing** tab in the dashboard sidebar.
6. **Self-improvement:** Manual only. Dante reviews dashboard, decides winner, manually disables losers and writes a new challenger. Spec must NOT implement any automatic promotion.

---

## Implementation plan — phased

Claude Code: do each phase in order. Verify each phase before moving on. Tell Dante to confirm each phase looks right before proceeding to the next.

---

### Phase 2.1 — Database schema

**File:** `agent/sql/migrations/2026_05_ab_testing.sql` (create new)

```sql
-- Subject line variants table
CREATE TABLE IF NOT EXISTS subject_variants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  subject_prompt TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Track which variant each outbound message used
ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS subject_variant_id UUID REFERENCES subject_variants(id);

-- Index for fast variant analytics queries
CREATE INDEX IF NOT EXISTS idx_messages_subject_variant
  ON messages(subject_variant_id)
  WHERE subject_variant_id IS NOT NULL;

-- Seed two starter variants (Dante can rename / edit these after migration)
INSERT INTO subject_variants (name, subject_prompt) VALUES
  (
    'Variant A — Direct',
    'Generate a short, direct subject line (under 8 words) for a cold outreach email. No emojis. No clickbait. Make it sound like a personal note from one person to another.'
  ),
  (
    'Variant B — Curiosity',
    'Generate a short, curiosity-driven subject line (under 8 words) for a cold outreach email. No emojis. Should make the recipient curious enough to open without feeling tricked.'
  )
ON CONFLICT DO NOTHING;
```

**Run instruction for Dante:** After commit, open Supabase SQL Editor and run the migration. Verify two starter variants exist by running `SELECT name, is_active FROM subject_variants;` — should return two rows.

---

### Phase 2.2 — Variant assignment at draft time

**Files to modify:** Whichever module is responsible for drafting emails — most likely `agent/src/services/draft.py` or similar. Find it via `grep -r "def.*draft" agent/src --include="*.py"`.

**Logic:**

1. When drafting an email for a lead:
   - Fetch all active subject variants from `subject_variants` where `is_active = true`
   - If 0 active variants: log a warning, fall back to current subject generation behavior, do not crash
   - If 1 active variant: use it for all leads (no actual A/B happening, but pipeline keeps working)
   - If 2+ active variants: pick one uniformly at random via `random.choice()`
2. Use that variant's `subject_prompt` when calling Gemini Pro to generate the subject line. **The body prompt is unchanged.** Two separate Gemini calls: one for subject (using variant), one for body (using existing prompt). If your current code generates subject + body in a single call, split it into two calls.
3. When inserting the message into Supabase, set `subject_variant_id` to the chosen variant's id.

**Important:**
- Do NOT change body generation behavior in any way.
- Do NOT change anything about hook tier selection. Hook tier and subject variant are independent.
- The split between subject prompt and body prompt should be done cleanly — if the current single prompt has subject and body instructions intertwined, refactor carefully so the body half is identical to today's behavior.

---

### Phase 2.3 — Dashboard: Prompt Variants section in Settings

**File:** `dashboard/src/app/settings/page.tsx` and a new component in `dashboard/src/components/settings/`.

Add a new section to the Settings page titled **"Subject Line Variants"** below the existing CTA section. The section shows:

- A list of all variants (active and inactive), each row showing:
  - Variant name (editable text input)
  - Subject prompt (editable textarea, ~5 rows tall)
  - Active toggle (checkbox or switch)
  - Save button (per row, saves that variant only — matches your existing settings pattern of "each field saves independently")
  - Delete button (with confirm dialog: "This will delete the variant. Past sends using it stay in the database. Continue?")
- A "+ New variant" button at the bottom that opens a row with empty fields

**API endpoints to add (in the FastAPI backend):**

```
GET    /api/variants                 → list all variants
POST   /api/variants                 → create new variant
PATCH  /api/variants/{id}            → update variant fields
DELETE /api/variants/{id}            → delete variant
```

All require existing JWT auth.

**Type definition (add to `dashboard/src/lib/types.ts`):**

```typescript
interface SubjectVariant {
  id: string;
  name: string;
  subject_prompt: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
```

Add corresponding methods to `dashboard/src/lib/api.ts` (`api.listVariants()`, `api.createVariant(...)`, etc.) and an SWR hook in `dashboard/src/lib/hooks/useVariants.ts`.

---

### Phase 2.4 — Dashboard: A/B Testing results tab

**Files to create:**
- `dashboard/src/app/ab-testing/page.tsx` (new route)
- `dashboard/src/components/ab-testing/VariantResultsTable.tsx`

**Sidebar nav:** Update `dashboard/src/components/layout/Sidebar.tsx` `NAV` array to add a new entry for `/ab-testing` between `/replies` and `/leads`. Use a fitting icon from lucide-react (e.g. `Beaker` or `FlaskConical`).

**Page content:** Render a `TopBar` with eyebrow "Helios / Experiments" and title "A/B Testing", followed by a results table.

**The results table:**

| Variant | Sends | Opens* | Replies | Booked | Reply rate | Book rate |
|---|---|---|---|---|---|---|
| Variant A — Direct | 142 | — | 18 | 3 | 12.7% | 2.1% |
| Variant B — Curiosity | 138 | — | 11 | 1 | 8.0% | 0.7% |

*Opens column shows `—` for v1 (open tracking is a future spec). Don't remove the column — just render `—`.

**Backend endpoint to add:**

```
GET /api/variants/stats  →  [
  {
    variant_id, name, is_active,
    sends, replies, booked,
    reply_rate, book_rate
  },
  ...
]
```

The stats are computed from the `messages` table:
- `sends` = count of outbound messages where `subject_variant_id = X` and `sent_at IS NOT NULL`
- `replies` = count of leads who received at least one outbound with `subject_variant_id = X` AND have at least one inbound message
- `booked` = count of leads who received at least one outbound with `subject_variant_id = X` AND have `status = 'booked'`
- `reply_rate` = replies / sends (return 0.0 if sends = 0)
- `book_rate` = booked / sends

Include both active and inactive variants in the response so Dante can see historical results from disabled variants.

**Bottom of the A/B Testing page:** include a small note in muted text:

> Statistical significance is not computed. With small sample sizes, treat these numbers as directional only. Wait for at least ~50 sends per variant before drawing conclusions.

This is important because Dante WILL look at 5 sends per variant and try to draw conclusions. The note doesn't stop that but at least documents the caveat.

---

### Phase 2.5 — Verification end-to-end

After all of 2.1–2.4 are implemented:

1. Drafting a batch of leads through the existing Draft button should produce a roughly 50/50 split across the two seed variants. Verify by running `SELECT subject_variant_id, COUNT(*) FROM messages WHERE direction = 'outbound' AND created_at > now() - interval '1 hour' GROUP BY subject_variant_id;` in Supabase.
2. The Settings page shows both variants and allows editing the name and prompt.
3. Toggling a variant inactive and drafting again should result in all new drafts using the remaining active variant.
4. The A/B Testing tab loads without errors and shows both variants with their current sends/replies counts.
5. Test send (Settings → Test Send) should still work normally — it should pick a variant just like real sends do.

---

## Verification checklist

Claude Code must verify all of these before reporting done:

- [ ] Migration file exists and was committed
- [ ] Drafting code is split into separate subject and body Gemini calls
- [ ] Active variants are fetched and one is randomly assigned per drafted message
- [ ] `subject_variant_id` is populated on every new outbound message
- [ ] Settings page has new "Subject Line Variants" section with full CRUD
- [ ] Sidebar has new "A/B Testing" entry
- [ ] `/ab-testing` page loads and shows the results table
- [ ] All four `/api/variants` endpoints work via curl (test each one)
- [ ] `/api/variants/stats` returns correct counts (verify against raw SQL)
- [ ] Type-check passes: `npx tsc --noEmit` in dashboard/
- [ ] Code committed and pushed to `DanteHelios/hermes` on `main`
- [ ] Vercel auto-deploys and the new pages render in prod

---

## What "done" looks like

Dante can:
1. Open Settings → Subject Line Variants → edit a prompt → hit Save → see it persist
2. Toggle a variant on/off
3. Run a draft batch → see new messages in the DB with `subject_variant_id` populated
4. Open the A/B Testing tab → see real numbers for each variant
5. After enough sends, decide one is winning → disable the loser → write a new challenger via the Settings UI → repeat

The whole loop is manual. There is no automation. Dante is the optimizer.

---

## Out of scope — DO NOT touch in this spec

- Body prompt variants (future)
- Hook tier A/B testing (future)
- Open rate tracking (separate spec)
- Statistical significance calculation (Dante can use an online calculator)
- Variant scheduling / rotation rules
- Cross-campaign variant restrictions
- Reply notifications (separate spec — should already be shipped before this one starts)
