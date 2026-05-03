"""Firecrawl fallback scraper for JS-rendered sites.

Only instantiated when FIRECRAWL_API_KEY is set. Used as a last-resort fetch
when HTTP scraping + extraction yields zero emails on a brokerage website
(typical for React/Next.js SPAs where contact data loads client-side).
"""

import structlog
from firecrawl import Firecrawl

from agent.src.config import settings
from agent.src.exceptions import FirecrawlError

log = structlog.get_logger(__name__)


class FirecrawlClient:
    def __init__(self) -> None:
        if not settings.FIRECRAWL_API_KEY:
            self._client: Firecrawl | None = None
        else:
            self._client = Firecrawl(api_key=settings.FIRECRAWL_API_KEY)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def scrape_html(self, url: str, timeout_ms: int = 30000) -> str | None:
        """Fetch a URL via Firecrawl's rendered-browser endpoint.

        Returns rendered HTML string on success, None on failure. Never raises
        to callers — logs and swallows so enrich() can continue without the
        fallback if Firecrawl is down.
        """
        if self._client is None:
            return None

        try:
            doc = self._client.scrape(
                url,
                formats=["html"],
                only_main_content=False,
                timeout=timeout_ms,
            )
        except Exception as e:
            log.warning(
                "firecrawl_scrape_failed",
                url=url,
                error_type=type(e).__name__,
                error=str(e),
            )
            return None

        html = getattr(doc, "html", None)
        if not html:
            log.warning("firecrawl_empty_html", url=url)
            return None

        log.info("firecrawl_scrape_success", url=url, content_length=len(html))
        return html


firecrawl_client = FirecrawlClient()
