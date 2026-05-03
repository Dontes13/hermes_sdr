import re
from pathlib import Path
from typing import Optional

import structlog
from jinja2 import Template
from pydantic import BaseModel

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

    supabase.table("leads").update(update).eq("id", lead_id).execute()
    return True
