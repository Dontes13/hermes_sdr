import re
from urllib.parse import urljoin, urlparse

import requests
import structlog
from bs4 import BeautifulSoup

log = structlog.get_logger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; HeliosSDR/1.0)"

# Matches email-like patterns shattered by inline HTML elements getting
# space-separated by BeautifulSoup's get_text(separator=' ').
# Examples:
#   "DAVIDFREED @ KW.COM"      -> "DAVIDFREED@KW.COM"
#   "davidfreed @ kw . com"    -> "davidfreed@kw.com"
_SHATTERED_EMAIL_RE = re.compile(
    r"([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9.-]+)\s*\.\s*([A-Za-z]{2,})"
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Tracking / platform / CDN domains that often appear inside <script> blobs
# (Sentry DSNs, Wix analytics, Next.js build metadata). Emails at these
# domains are never a brokerage's actual contact address.
_SCRIPT_EMAIL_NOISE_DOMAINS = (
    "sentry.io", "sentry.wixpress.com", "wixpress.com", "cloudinary.com",
    "googleapis.com", "gstatic.com", "doubleclick.net", "facebook.com",
    "google-analytics.com", "mapbox.com", "segment.io", "polyfill.io",
    "jsdelivr.net", "cloudflare.com", "schema.org", "w3.org",
    "example.com", "example.org", "amazonaws.com",
)


def _harvest_script_emails(soup: "BeautifulSoup") -> list[str]:
    """Scan every <script> tag's body for email addresses.

    Next.js/React brokerage sites (Compass, Luxury Presence, etc.) frequently
    bake contact data into a JSON blob inside <script id="__NEXT_DATA__">.
    Those emails never reach the DOM text and get wiped when we decompose
    <script> in extract_text. This harvests them first, filtering out
    tracking/CDN noise domains.

    Returns deduped list preserving first-seen order.
    """
    harvested: list[str] = []
    seen: set[str] = set()
    for script in soup.find_all("script"):
        body = script.string or script.get_text() or ""
        if not body:
            continue
        for email in _EMAIL_RE.findall(body):
            lower = email.lower()
            if lower in seen:
                continue
            domain = lower.split("@", 1)[1]
            if any(nd in domain for nd in _SCRIPT_EMAIL_NOISE_DOMAINS):
                continue
            seen.add(lower)
            harvested.append(email)
    return harvested


def _restore_shattered_emails(text: str) -> str:
    """Real estate sites frequently wrap the @ symbol of an email in its own
    inline element (e.g. <span class="at">@</span>) as a lightweight
    anti-scraper measure. BeautifulSoup's get_text(separator=' ') then
    produces "name @ domain . com" which breaks verbatim-substring email
    verification in enrich.py's _verify_email guard.

    This function finds shattered patterns and APPENDS normalized forms
    to the end of the text (rather than replacing in-place). Appending
    preserves original context while also ensuring the normalized form
    is present verbatim somewhere in the string.

    Skips any normalized email that is already present in the text, and
    dedupes within the appended block.
    """
    matches = _SHATTERED_EMAIL_RE.findall(text)
    if not matches:
        return text

    text_lower = text.lower()
    restored: list[str] = []
    seen: set[str] = set()

    for local, domain, tld in matches:
        email = f"{local}@{domain}.{tld}".lower()
        # Skip if the normalized form is already in text verbatim
        if email in text_lower:
            continue
        if email in seen:
            continue
        seen.add(email)
        restored.append(email)

    if not restored:
        return text

    block = "\n\n--- RESTORED EMAILS ---\n"
    block += "\n".join(f"EMAIL: {e}" for e in restored)
    return text + block


def fetch(url: str, timeout: int = 10) -> str | None:
    """GET a URL and return HTML on success, None on any failure. Never raises."""
    try:
        session = requests.Session()
        session.max_redirects = 5
        resp = session.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
            timeout=timeout,
            allow_redirects=True,
        )
        MAX_RESPONSE_BYTES = 5_000_000  # 5MB
        if len(resp.content) > MAX_RESPONSE_BYTES:
            log.warning(
                "scrape_oversized",
                url=url,
                size_bytes=len(resp.content),
            )
            return None
        if not resp.ok:
            log.warning(
                "scrape_non_2xx",
                url=url,
                final_url=resp.url,
                status=resp.status_code,
            )
            return None

        log.info(
            "scrape_fetched",
            url=url,
            final_url=resp.url,
            status=resp.status_code,
            content_length=len(resp.text),
            redirects=len(resp.history),
        )
        return resp.text
    except Exception as e:
        log.warning(
            "scrape_failed", url=url, error_type=type(e).__name__, error=str(e)
        )
        return None


def extract_text(html: str, max_chars: int = 8000) -> str:
    """Strip tags/chrome from HTML, return cleaned text truncated to max_chars.

    Preserves mailto: email addresses from anywhere in the original HTML
    (even inside decomposed chrome like <footer>).
    """
    soup = BeautifulSoup(html, "lxml")

    # STEP 1: Harvest every mailto email from the ORIGINAL soup before
    # any decomposition. This guarantees footer/header emails survive.
    harvested_emails: list[str] = []
    seen_emails: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip()
            if email and email.lower() not in seen_emails:
                seen_emails.add(email.lower())
                harvested_emails.append(email)

    # STEP 1b: Harvest emails from <script> bodies before they get decomposed.
    # Covers Next.js/React sites that bake contact data into JSON blobs.
    for email in _harvest_script_emails(soup):
        lower = email.lower()
        if lower not in seen_emails:
            seen_emails.add(lower)
            harvested_emails.append(email)

    # STEP 2: Strip noisy chrome. We KEEP <header> because real estate
    # sites put contact info there.
    for tag in soup(["script", "style", "nav"]):
        tag.decompose()

    # STEP 3: Get visible text and collapse whitespace
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    text = text[:max_chars]

    # STEP 4: Append harvested mailto emails as a plain-text block at
    # the end. This survives truncation because we add it AFTER the cut.
    # Each email is on its own line prefixed with "EMAIL:" so Gemini
    # can't miss it.
    if harvested_emails:
        email_block = "\n\n--- HARVESTED EMAILS ---\n"
        email_block += "\n".join(f"EMAIL: {e}" for e in harvested_emails)
        text = text + email_block

    # STEP 5: Restore emails shattered by inline @ symbol elements
    # (common anti-scraper pattern on real estate sites, e.g. Luxury Presence).
    text = _restore_shattered_emails(text)

    return text


def find_subpage_links(
    base_url: str,
    html: str,
    max_pages: int = 5,
) -> list[str]:
    """Return same-domain subpage URLs prioritized by contact-relevance.

    Hardcoded priority buckets — no more keywords parameter.
    """
    soup = BeautifulSoup(html, "lxml")
    base_domain = urlparse(base_url).netloc

    NOISE_PATTERNS = [
        "blog", "listing", "property", "properties", "search",
        "login", "register", "signin", "signup", "/page/",
        ".pdf", ".jpg", ".jpeg", ".png", ".gif",
    ]

    buckets: dict[int, list[str]] = {1: [], 2: [], 3: [], 4: []}
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)

        if parsed.netloc != base_domain:
            continue
        if absolute in seen:
            continue

        path_lower = parsed.path.lower()

        if any(noise in path_lower for noise in NOISE_PATTERNS):
            continue

        priority = None
        if any(kw in path_lower for kw in ["contact", "reach", "get-in-touch"]):
            priority = 1
        elif any(kw in path_lower for kw in ["about", "our-story", "who-we-are"]):
            priority = 2
        elif any(kw in path_lower for kw in ["team", "meet", "staff", "leadership"]):
            priority = 3
        elif "agent" in path_lower:
            priority = 4

        if priority is None:
            continue

        seen.add(absolute)
        buckets[priority].append(absolute)

    # Flatten in priority order, cap at max_pages
    result: list[str] = []
    for p in sorted(buckets.keys()):
        for url in buckets[p]:
            result.append(url)
            if len(result) >= max_pages:
                return result
    return result
