"""Apollo lead sourcing — two-step (search → reveal) flow.

`source_leads_from_apollo()` runs an Apollo people search and returns
candidates with LOCKED emails — no credit is spent. The user picks; only the
picked candidates get a `/people/match` reveal call (1 credit each) via
`reveal_and_persist()`, which writes them to `leads` with source='apollo'.

Design notes (Phase B decisions):
- Apollo leads are inserted as status='enriched' (NOT 'new'): we deliberately
  skip the website-scrape enrich pass so it can't overwrite the email we just
  spent a credit to reveal. Drafts read intel_json + lead fields and degrade
  gracefully without scrape-derived intel.
- `vertical` is mapped from Apollo's `industry` string via a small keyword
  map (Google Places leads get vertical from intel_json.types instead).
- Dedup: apollo_id (intel_json->>'apollo_id') is checked BEFORE the reveal
  call so a duplicate never costs a credit; revealed email is a secondary
  guard. The google_places prospect() path is untouched.
"""

import structlog

from agent.src.clients.apollo import apollo_client
from agent.src.clients.supabase_client import supabase
from agent.src.functions.enrich import score_lead

log = structlog.get_logger(__name__)

# Cap on candidates returned by a single search call.
_MAX_SEARCH_LIMIT = 100


def _industry_to_vertical(industry: str | None) -> str:
    """Map an Apollo `industry` string to our vertical enum.

    Mirrors the values the 2026_06_icp_score.sql backfill produced for Google
    Places leads (real_estate / restaurant / other) so the dashboard's
    vertical badge is consistent across sources. Falls back to 'other'.
    """
    if not industry:
        return "other"
    s = industry.lower()
    if any(k in s for k in ("real estate", "realty", "realtor", "brokerage", "property")):
        return "real_estate"
    if any(k in s for k in ("restaurant", "food", "cafe", "coffee", "dining", "hospitality")):
        return "restaurant"
    return "other"


def _is_locked_email(email: str | None) -> bool:
    """True if Apollo didn't actually unlock a usable address.

    Search results (and failed reveals) come back with a placeholder like
    `email_not_unlocked@domain.com`.
    """
    if not email:
        return True
    return "not_unlocked" in email.lower() or "domain.com" == email.lower().split("@")[-1]


def _org_of(person: dict) -> dict:
    return person.get("organization") or person.get("account") or {}


def _candidate_from_person(person: dict, existing_apollo_ids: set[str]) -> dict:
    """Shape one search-result person into a candidate.

    Per the Phase A contract: email is omitted, `email_locked` is always True
    at search stage, and `email_status` is exposed so the user can judge
    whether a reveal is worth a credit before spending one.
    """
    org = _org_of(person)
    apollo_id = person.get("id")
    return {
        "apollo_id": apollo_id,
        "name": person.get("name")
        or " ".join(
            p for p in (person.get("first_name"), person.get("last_name")) if p
        )
        or None,
        "title": person.get("title"),
        "company": org.get("name"),
        "website": org.get("website_url") or org.get("primary_domain"),
        "linkedin_url": person.get("linkedin_url"),
        "city": person.get("city"),
        "estimated_employees": org.get("estimated_num_employees"),
        "industry": org.get("industry"),
        "email_status": person.get("email_status"),
        "email_locked": True,
        "already_in_db": apollo_id in existing_apollo_ids,
    }


def _build_search_filters(target: str, city: str) -> dict:
    """Translate the campaign's free-text target/city into Apollo search
    params. Kept intentionally simple: `q_keywords` carries the target and
    `person_locations` carries the city. Apollo treats both as fuzzy, which
    matches how the Google Places text query worked.
    """
    filters: dict = {}
    if target and target.strip():
        filters["q_keywords"] = target.strip()
    if city and city.strip():
        filters["person_locations"] = [city.strip()]
    return filters


def _existing_dedup_keys() -> tuple[set[str], set[str]]:
    """Return (apollo_ids, lowercased emails) already present in leads.

    Small-data approach: the leads table is in the dozens, so one select is
    cheaper and more robust than per-id JSON-arrow filters.
    """
    resp = supabase.table("leads").select("email, intel_json").execute()
    apollo_ids: set[str] = set()
    emails: set[str] = set()
    for row in resp.data or []:
        intel = row.get("intel_json") or {}
        aid = intel.get("apollo_id")
        if aid:
            apollo_ids.add(aid)
        email = row.get("email")
        if email:
            emails.add(email.lower())
    return apollo_ids, emails


def source_leads_from_apollo(
    target: str,
    city: str,
    campaign_id: str | None = None,
    limit: int = 25,
    page: int = 1,
    use_mixed: bool = True,
) -> dict:
    """Run an Apollo people search and return candidates (no credits spent).

    Returns a dict with pagination metadata and a `candidates` list. Each
    candidate carries `already_in_db` so the UI can grey out leads we already
    have. Emails are never included here — they're locked until reveal.
    """
    per_page = max(1, min(limit, _MAX_SEARCH_LIMIT))
    filters = _build_search_filters(target, city)

    if not apollo_client.enabled:
        log.warning("apollo_search_skipped", reason="disabled")
        return {
            "campaign_id": campaign_id,
            "page": page,
            "per_page": per_page,
            "total_entries": 0,
            "total_pages": 0,
            "candidates": [],
            "error": "apollo_disabled",
        }

    search = (
        apollo_client.mixed_people_search
        if use_mixed
        else apollo_client.people_search
    )
    data = search(page=page, per_page=per_page, **filters)
    if data is None:
        return {
            "campaign_id": campaign_id,
            "page": page,
            "per_page": per_page,
            "total_entries": 0,
            "total_pages": 0,
            "candidates": [],
            "error": "apollo_request_failed",
        }

    # mixed_people/search returns both net-new `people` and already-in-account
    # `contacts`; merge them. people/search returns just `people`.
    people = list(data.get("people") or [])
    if use_mixed:
        people += list(data.get("contacts") or [])

    existing_apollo_ids, _ = _existing_dedup_keys()
    candidates = [
        _candidate_from_person(p, existing_apollo_ids)
        for p in people
        if p.get("id")
    ]

    pagination = data.get("pagination") or {}
    log.info(
        "apollo_search_complete",
        campaign_id=campaign_id,
        returned=len(candidates),
        total_entries=pagination.get("total_entries"),
    )
    return {
        "campaign_id": campaign_id,
        "page": pagination.get("page", page),
        "per_page": pagination.get("per_page", per_page),
        "total_entries": pagination.get("total_entries", 0),
        "total_pages": pagination.get("total_pages", 0),
        "candidates": candidates,
    }


def _persist_apollo_lead(person: dict, campaign_id: str | None, fallback_city: str) -> dict:
    """Map a revealed Apollo person to a lead row, ICP-score it, insert it,
    and return the inserted row. Caller guarantees the email is unlocked.
    """
    org = _org_of(person)
    apollo_id = person.get("id")
    email = person.get("email")
    name = person.get("name") or " ".join(
        p for p in (person.get("first_name"), person.get("last_name")) if p
    ) or None
    title = person.get("title")
    website = org.get("website_url") or org.get("primary_domain")
    industry = org.get("industry")
    estimated_employees = org.get("estimated_num_employees")
    email_status = person.get("email_status")
    phone = org.get("phone")
    if not phone:
        primary_phone = org.get("primary_phone") or {}
        phone = primary_phone.get("number") if isinstance(primary_phone, dict) else None

    vertical = _industry_to_vertical(industry)

    intel_json: dict = {
        "apollo_id": apollo_id,
        "title": title,
        "email_status": email_status,
        "industry": industry,
        "estimated_employees": estimated_employees,
        "year_founded": org.get("founded_year"),
        "apollo": {
            "contact": {
                "name": name,
                "title": title,
                "linkedin_url": person.get("linkedin_url"),
                "email_status": email_status,
            },
            "org": {
                "name": org.get("name"),
                "headcount": estimated_employees,
                "industry": industry,
                "founded_year": org.get("founded_year"),
            },
        },
    }

    icp_score, icp_reasons = score_lead(
        {
            "email": email,
            "email_status": email_status,
            "estimated_employees": estimated_employees,
            "website": website,
            "owner_name": name,
        },
        source="apollo",
    )

    lead_row: dict = {
        "company": org.get("name") or "(unknown company)",
        "city": person.get("city") or fallback_city or "Unknown",
        "website": website,
        "email": email,
        "owner_name": name,
        "phone": phone,
        "linkedin_url": person.get("linkedin_url"),
        "intel_json": intel_json,
        "status": "enriched",
        "source": "apollo",
        "icp_score": icp_score,
        "icp_score_reasons": icp_reasons,
        "vertical": vertical,
    }
    if campaign_id:
        lead_row["campaign_id"] = campaign_id

    insert_resp = supabase.table("leads").insert(lead_row).execute()
    return insert_resp.data[0]


def reveal_and_persist(
    apollo_person_ids: list[str], campaign_id: str | None = None
) -> dict:
    """Reveal each picked Apollo person (1 credit each) and persist as a lead.

    Dedup on apollo_id is checked BEFORE the reveal call, so a duplicate never
    spends a credit. Revealed email is a secondary dedup guard (after a credit
    is spent — reported honestly in credits_used). Returns added / skipped /
    credits_used.
    """
    existing_apollo_ids, existing_emails = _existing_dedup_keys()

    fallback_city = ""
    if campaign_id:
        camp = (
            supabase.table("campaigns")
            .select("city")
            .eq("id", campaign_id)
            .limit(1)
            .execute()
        )
        if camp.data:
            fallback_city = camp.data[0].get("city") or ""

    added: list[dict] = []
    skipped: list[dict] = []
    credits_used = 0

    for apollo_id in apollo_person_ids:
        # Dedup BEFORE spending a credit.
        if apollo_id in existing_apollo_ids:
            skipped.append({"apollo_id": apollo_id, "reason": "already_in_db"})
            continue

        person = apollo_client.reveal_person_by_id(apollo_id)
        credits_used += 1  # /people/match consumes a credit even if no email

        if not person:
            skipped.append({"apollo_id": apollo_id, "reason": "reveal_failed"})
            continue

        email = person.get("email")
        if _is_locked_email(email):
            skipped.append({"apollo_id": apollo_id, "reason": "no_email_revealed"})
            continue

        if email.lower() in existing_emails:
            skipped.append({"apollo_id": apollo_id, "reason": "already_in_db"})
            continue

        try:
            lead = _persist_apollo_lead(person, campaign_id, fallback_city)
        except Exception as exc:
            log.warning(
                "apollo_persist_failed", apollo_id=apollo_id, error=str(exc)
            )
            skipped.append({"apollo_id": apollo_id, "reason": "persist_failed"})
            continue

        # Keep in-batch dedup tight so a repeated id in the same request can't
        # double-insert.
        existing_apollo_ids.add(apollo_id)
        existing_emails.add(email.lower())
        added.append(
            {
                "id": lead["id"],
                "company": lead["company"],
                "email": lead["email"],
                "icp_score": lead["icp_score"],
                "vertical": lead["vertical"],
                "status": lead["status"],
                "source": lead["source"],
            }
        )
        log.info(
            "apollo_lead_added",
            apollo_id=apollo_id,
            lead_id=lead["id"],
            campaign_id=campaign_id,
            icp_score=lead["icp_score"],
        )

    return {
        "campaign_id": campaign_id,
        "requested": len(apollo_person_ids),
        "credits_used": credits_used,
        "added": added,
        "skipped": skipped,
    }
