import re
from pathlib import Path
from typing import Optional

import structlog
from jinja2 import Template
from pydantic import BaseModel

from agent.src.clients.apollo import _extract_domain, apollo_client
from agent.src.clients.firecrawl import firecrawl_client
from agent.src.clients.gemini import gemini
from agent.src.clients.supabase_client import supabase
from agent.src.utils.scraper import extract_text, fetch, find_subpage_links

log = structlog.get_logger(__name__)

_EMAIL_IN_TEXT_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Personal LinkedIn profile URLs only (linkedin.com/in/<handle>). Excludes
# /company/ and /school/ pages — those aren't messageable.
_LINKEDIN_URL_RE = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?",
    re.IGNORECASE,
)


def _extract_linkedin_url(html_or_text: str) -> Optional[str]:
    """Find the first personal LinkedIn profile URL in the input. Returns
    a normalized URL (scheme + host + /in/<handle>) or None.

    Best-effort only: many real-estate sites don't link the agent's
    LinkedIn from the homepage. We don't fall back to off-site search —
    keeps enrichment cheap and deterministic.
    """
    if not html_or_text:
        return None
    match = _LINKEDIN_URL_RE.search(html_or_text)
    if not match:
        return None
    url = match.group(0).rstrip("/")
    # Strip query/fragment if any made it through
    for sep in ("?", "#"):
        if sep in url:
            url = url.split(sep, 1)[0]
    return url


def _verify_email(
    email: Optional[str],
    source_text: str,
    lead_id: str,
    company: str,
) -> Optional[str]:
    """Return the email only if it appears verbatim (case-insensitive) in
    source_text. Otherwise log a warning and return None.

    This is the hallucination guard: Gemini occasionally invents plausible
    email addresses that don't exist on the source site. Sending to
    fabricated addresses tanks sender reputation. We reject anything not
    literally present in the scraped text.

    Known limitation: obfuscated emails like "mike [at] foo [dot] com"
    will not match and will be rejected as a false negative. This is
    preferable to the alternative.
    """
    if not email:
        return None
    if email.lower() in source_text.lower():
        return email
    log.warning(
        "hallucinated_email_rejected",
        lead_id=lead_id,
        rejected_email=email,
        company=company,
    )
    return None


ENRICH_TEMPLATE = Template(
    (Path(__file__).parent.parent / "prompts" / "enrich.j2").read_text()
)


class EnrichResult(BaseModel):
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    general_email: Optional[str] = None
    agent_count: Optional[int] = None
    year_founded: Optional[int] = None
    slogan: Optional[str] = None
    markets_served: list[str] = []
    specialties: list[str] = []
    value_prop: Optional[str] = None
    notable_facts: list[str] = []


def score_lead(lead: dict, source: str = "google_places") -> tuple[int, dict]:
    """Score a lead 0–100 based on available enrichment signals.

    Google Places leads carry: owner_email, general_email (both sourced from
    intel_json, not the top-level email column), google_reviews, website,
    owner_name.

    Apollo leads (source="apollo") arrive differently: the revealed email is
    top-level (no owner/general split) and is attached to a named person +
    title, so it counts as a named-contact email. Apollo has no Google review
    count, so the "company quality" dimension uses Apollo firmographics
    instead — email deliverability (email_status) and company size
    (estimated_employees) — with a comparable point ceiling so the two
    sources score on roughly the same scale.

    The email / website / owner dimensions are identical across sources; only
    the third (company-quality) signal branches. Return shape is unchanged so
    icp_score_reasons stays uniform across both sources.
    """
    score = 0
    reasons: dict = {}

    # Email. For Apollo, fall back to the top-level `email` (a named contact's
    # revealed address) when the owner/general split isn't present.
    owner_email = lead.get("owner_email")
    if not owner_email and source == "apollo":
        owner_email = lead.get("email")
    general_email = lead.get("general_email")
    if owner_email:
        score += 40
        reasons["named_owner_email"] = 40
    elif general_email and not any(
        general_email.startswith(p)
        for p in ("info@", "hello@", "contact@", "admin@")
    ):
        score += 25
        reasons["named_email"] = 25
    elif general_email:
        score += 10
        reasons["generic_email_only"] = 10

    # Company-quality signal — differs by source.
    if source == "apollo":
        if lead.get("email_status") == "verified":
            score += 15
            reasons["verified_email"] = 15
        employees = lead.get("estimated_employees") or 0
        if 2 <= employees <= 500:
            score += 10
            reasons["company_size_fit"] = 10
        elif employees > 500:
            score += 5
            reasons["large_company"] = 5
    else:
        reviews = lead.get("google_reviews") or 0
        if 50 <= reviews <= 500:
            score += 25
            reasons["healthy_review_count"] = 25
        elif reviews > 500:
            score += 15
            reasons["established_business"] = 15
        elif reviews >= 10:
            score += 5
            reasons["some_reviews"] = 5

    if lead.get("website"):
        score += 10
        reasons["has_website"] = 10

    if lead.get("owner_name"):
        score += 10
        reasons["owner_identified"] = 10

    return min(score, 100), reasons


def enrich(lead_id: str) -> bool:
    """Scrape lead website, extract intel via Gemini Flash, update lead.

    Returns True if enrichment ran successfully (even if lead is dead due
    to missing email). Returns False only on hard failure (no website,
    fetch crashed).
    """
    # 1. Load lead
    lead_resp = (
        supabase.table("leads").select("*").eq("id", lead_id).single().execute()
    )
    lead = lead_resp.data
    intel = lead.get("intel_json") or {}

    # 2. No website → dead
    if not lead.get("website"):
        supabase.table("leads").update(
            {
                "status": "dead",
                "intel_json": {**intel, "dead_reason": "no_website"},
            }
        ).eq("id", lead_id).execute()
        log.warning("enrich_no_website", lead_id=lead_id, company=lead["company"])
        return False

    # 3. Fetch homepage
    html = fetch(lead["website"])
    if html is None:
        supabase.table("leads").update(
            {
                "status": "dead",
                "intel_json": {**intel, "scrape_error": "homepage_fetch_failed"},
            }
        ).eq("id", lead_id).execute()
        log.warning("enrich_fetch_failed", lead_id=lead_id, company=lead["company"])
        return False

    # 4. Collect page texts — homepage first
    pages = [extract_text(html)]

    # 5. Find and fetch subpage links (priority-ordered, cap at 5)
    subpage_urls = find_subpage_links(
        base_url=lead["website"],
        html=html,
        max_pages=5,
    )

    for url in subpage_urls:
        sub_html = fetch(url)
        if sub_html is not None:
            pages.append(extract_text(sub_html))

    # 6. Concatenate all page texts
    page_text = "\n\n--- PAGE BREAK ---\n\n".join(pages)

    # 6a. Firecrawl fallback: if HTTP scraping turned up zero emails across
    # all pages, the site is likely a JS-rendered SPA. Re-fetch the homepage
    # with Firecrawl's browser-rendered endpoint and append to page_text.
    # Fires at most once per lead, only on leads that would otherwise die.
    used_firecrawl = False
    if firecrawl_client.enabled and not _EMAIL_IN_TEXT_RE.search(page_text):
        log.info(
            "firecrawl_fallback_triggered",
            lead_id=lead_id,
            company=lead["company"],
            homepage=lead["website"],
        )
        rendered_html = firecrawl_client.scrape_html(lead["website"])
        if rendered_html:
            rendered_text = extract_text(rendered_html)
            page_text = (
                page_text + "\n\n--- FIRECRAWL RENDER ---\n\n" + rendered_text
            )
            used_firecrawl = True

    # Store first 2000 chars of page_text for debugging extraction failures
    # without needing to re-scrape
    debug_snippet = page_text[:2000]

    # 7. Render prompt
    prompt = ENRICH_TEMPLATE.render(
        company=lead["company"],
        city=lead["city"],
        page_text=page_text,
    )

    # 8. Call Gemini Flash
    result = gemini.generate_json_flash(prompt, EnrichResult)

    # 8a. Hallucination guard — reject emails not found verbatim in scraped text
    verified_owner_email = _verify_email(
        result.owner_email, page_text, lead_id, lead["company"]
    )
    verified_general_email = _verify_email(
        result.general_email, page_text, lead_id, lead["company"]
    )

    result_dict = result.model_dump()
    result_dict["owner_email"] = verified_owner_email
    result_dict["general_email"] = verified_general_email

    # 9. Merge into intel_json — preserve existing keys (place_id, address, types)
    merged_intel = {**intel}
    for k, v in result_dict.items():
        if v is not None and v != [] and v != "":
            merged_intel[k] = v
    merged_intel["debug_page_text"] = debug_snippet
    if used_firecrawl:
        merged_intel["firecrawl_fallback_used"] = True

    # 10. Determine email and owner
    email = verified_owner_email or verified_general_email
    owner_name = result.owner_name

    # 10a. LinkedIn profile discovery — best-effort scan of raw homepage
    # HTML (where href= lives) then concatenated page text. Not finding a
    # URL is fine; LinkedIn channel is opt-in per lead anyway.
    linkedin_url = _extract_linkedin_url(html) or _extract_linkedin_url(page_text)

    # 10b. Apollo enrichment — optional, fires only when APOLLO_API_KEY is set.
    # Never blocks enrichment on failure; all errors are caught inside the client.
    if apollo_client.enabled:
        domain = _extract_domain(lead["website"])
        apollo_contact: dict | None = None
        apollo_org: dict | None = None
        try:
            if email and domain:
                apollo_contact = apollo_client.enrich_contact(
                    email=email, domain=domain
                )
            if domain:
                apollo_org = apollo_client.enrich_organization(domain=domain)
        except Exception as exc:
            log.warning("apollo_enrichment_error", lead_id=lead_id, error=str(exc))

        apollo_intel: dict = {}
        if apollo_contact:
            apollo_intel["contact"] = apollo_contact
            if apollo_contact.get("name") and not owner_name:
                owner_name = apollo_contact["name"]
            if apollo_contact.get("linkedin_url") and not linkedin_url:
                linkedin_url = apollo_contact["linkedin_url"]
        if apollo_org:
            apollo_intel["org"] = apollo_org
            if apollo_org.get("founded_year") and not merged_intel.get("year_founded"):
                merged_intel["year_founded"] = apollo_org["founded_year"]
            if apollo_org.get("headcount") and not merged_intel.get("agent_count"):
                merged_intel["estimated_employees"] = apollo_org["headcount"]
        if apollo_intel:
            merged_intel["apollo"] = apollo_intel

    update: dict = {
        "intel_json": merged_intel,
        "owner_name": owner_name,
        "email": email,
    }
    if linkedin_url:
        update["linkedin_url"] = linkedin_url

    # 11. Set status based on whether we found an email
    if email is None:
        merged_intel["dead_reason"] = "no_email_found"
        update["intel_json"] = merged_intel
        update["status"] = "dead"
        log.info("enrich_no_email", lead_id=lead_id, company=lead["company"])
    else:
        update["status"] = "enriched"
        log.info(
            "enrich_success", lead_id=lead_id, company=lead["company"], email=email
        )

    # 12. ICP score — uses local variables so we don't re-fetch the row
    icp_score, icp_reasons = score_lead(
        {
            "owner_email": verified_owner_email,
            "general_email": verified_general_email,
            "google_reviews": lead.get("google_reviews"),
            "website": lead.get("website"),
            "owner_name": owner_name,
        }
    )
    update["icp_score"] = icp_score
    update["icp_score_reasons"] = icp_reasons

    supabase.table("leads").update(update).eq("id", lead_id).execute()
    return True
