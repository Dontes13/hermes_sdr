-- subject_prompt already exists as of 2026_05_ab_testing.sql. This migration is a no-op and exists for documentation only.
--
-- subject_variants.subject_prompt serves as the per-variant system prompt injected
-- into subject.j2 at draft time. It was created with the initial schema migration
-- and is already used by draft.py for fully DB-driven subject line generation.
--
-- The UPDATE statements below are safe to re-run: they restore the original seed
-- prompt copy in case it was accidentally wiped. They do NOT change any schema.

UPDATE subject_variants
  SET subject_prompt = 'Generate a short, direct subject line (under 8 words) for a cold outreach email. No emojis. No clickbait. Make it sound like a personal note from one person to another.'
  WHERE name = 'Variant A — Direct';

UPDATE subject_variants
  SET subject_prompt = 'Generate a short, curiosity-driven subject line (under 8 words) for a cold outreach email. No emojis. Should make the recipient curious enough to open without feeling tricked.'
  WHERE name = 'Variant B — Curiosity';
