#!/usr/bin/env python3
"""Backfill icp_score and icp_score_reasons for all existing leads.

Run from the repo root after the 2026_06_icp_score.sql migration:
    .venv/bin/python scripts/backfill_icp_scores.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

# Satisfy required env vars that aren't needed for this script
for _k in ("GEMINI_API_KEY", "GOOGLE_PLACES_API_KEY", "AGENTMAIL_API_KEY",
           "DASHBOARD_PASSWORD", "JWT_SECRET"):
    os.environ.setdefault(_k, "placeholder")

from src.clients.supabase_client import supabase  # noqa: E402
from src.functions.enrich import score_lead  # noqa: E402

leads = supabase.table("leads").select("*").execute().data
print(f"Scoring {len(leads)} leads...")

score_buckets = {">=70": [], "40-69": [], "<40": []}
vertical_counts: dict[str, int] = {}
updated = 0

for lead in leads:
    intel = lead.get("intel_json") or {}
    score_input = {
        "owner_email": intel.get("owner_email"),
        "general_email": intel.get("general_email"),
        "google_reviews": lead.get("google_reviews"),
        "website": lead.get("website"),
        "owner_name": lead.get("owner_name"),
    }
    icp_score, icp_reasons = score_lead(score_input)

    supabase.table("leads").update(
        {"icp_score": icp_score, "icp_score_reasons": icp_reasons}
    ).eq("id", lead["id"]).execute()
    updated += 1

    # Bucket
    if icp_score >= 70:
        score_buckets[">=70"].append(lead["company"])
    elif icp_score >= 40:
        score_buckets["40-69"].append(lead["company"])
    else:
        score_buckets["<40"].append(lead["company"])

    # Vertical (already set by migration, just for reporting)
    v = lead.get("vertical") or "null"
    vertical_counts[v] = vertical_counts.get(v, 0) + 1

print(f"\nUpdated {updated}/{len(leads)} leads.")

print("\n=== SCORE DISTRIBUTION ===")
for bucket, companies in score_buckets.items():
    print(f"  {bucket}: {len(companies)}")
    for c in companies:
        print(f"    - {c}")

print("\n=== VERTICAL DISTRIBUTION (from DB — set by migration) ===")
for v, cnt in sorted(vertical_counts.items(), key=lambda x: -x[1]):
    print(f"  {v}: {cnt}")
