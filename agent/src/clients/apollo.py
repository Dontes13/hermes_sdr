"""Apollo.io enrichment client.

Optional — disabled when APOLLO_API_KEY is unset. Never raises to callers;
logs and returns None on any failure so the enrichment pipeline degrades
gracefully without Apollo data.

Rate guard: enforces a minimum interval between calls so a busy tick
can't burst into Apollo's per-minute limit. On HTTP 429 the call is
abandoned immediately (not retried) to avoid compounding the problem —
the lead just enriches without Apollo data.
"""

import threading
import time
from urllib.parse import urlparse

import requests
import structlog

from agent.src.config import settings

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.apollo.io/v1"
_TIMEOUT_S = 15
# Conservative floor: 1 call/second keeps us well under Apollo's lowest
# documented limit (10 req/min on some free tiers = 1 per 6 s). Adjust up
# if on a paid plan where limits are higher.
_MIN_INTERVAL_S = 1.0


class ApolloClient:
    def __init__(self) -> None:
        self._api_key = settings.APOLLO_API_KEY
        self._lock = threading.Lock()
        self._last_call_at: float = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def _throttle(self) -> None:
        with self._lock:
            now = time.monotonic()
            gap = _MIN_INTERVAL_S - (now - self._last_call_at)
            if gap > 0:
                time.sleep(gap)
            self._last_call_at = time.monotonic()

    def _post(self, path: str, payload: dict) -> dict | None:
        if not self._api_key:
            log.warning("apollo_disabled", reason="no_api_key")
            return None

        # Log input sans API key
        safe_payload = {k: v for k, v in payload.items() if k != "api_key"}
        log.info("apollo_call_start", path=path, payload=safe_payload)

        self._throttle()

        try:
            resp = requests.post(
                f"{_BASE_URL}{path}",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self._api_key,
                    "Cache-Control": "no-cache",
                },
                timeout=_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            log.warning("apollo_request_failed", path=path, error=str(exc))
            return None

        try:
            _body_keys = list(resp.json().keys()) if resp.ok else None
        except Exception:
            _body_keys = None
        log.info(
            "apollo_response",
            path=path,
            status=resp.status_code,
            response_keys=_body_keys,
            response_text_snippet=resp.text[:300] if not resp.ok else None,
        )

        if resp.status_code == 429:
            log.warning("apollo_rate_limited", path=path)
            return None

        if resp.status_code == 422:
            log.info("apollo_no_match", path=path, payload=safe_payload)
            return None

        if not resp.ok:
            log.warning("apollo_api_error", path=path, status=resp.status_code,
                        body_snippet=resp.text[:300])
            return None

        try:
            data = resp.json()
        except Exception as exc:
            log.warning("apollo_parse_error", path=path, error=str(exc))
            return None

        return data

    def enrich_contact(self, email: str, domain: str | None = None) -> dict | None:
        """Enrich a contact by email.

        Returns a normalized dict with any subset of:
          name, title, linkedin_url, tenure_start (ISO date string of
          current-role start).
        Returns None if Apollo is disabled, the contact wasn't found, or
        any error occurs.
        """
        if not self.enabled:
            log.warning("apollo_contact_skipped", reason="disabled", email=email)
            return None

        payload: dict = {"email": email, "reveal_personal_emails": False}
        if domain:
            payload["domain"] = domain

        data = self._post("/people/match", payload)
        if not data or not data.get("person"):
            log.info("apollo_contact_no_person", email=email,
                     top_level_keys=list(data.keys()) if data else None)
            return None

        person = data["person"]
        result: dict = {}

        if person.get("name"):
            result["name"] = person["name"]
        if person.get("title"):
            result["title"] = person["title"]
        if person.get("linkedin_url"):
            result["linkedin_url"] = person["linkedin_url"]

        history = person.get("employment_history") or []
        current = next(
            (e for e in history if e.get("current") or not e.get("end_date")),
            None,
        )
        if current and current.get("start_date"):
            result["tenure_start"] = current["start_date"]

        if result:
            log.info("apollo_contact_enriched", email=email, fields=list(result.keys()))
        return result or None

    def enrich_organization(self, domain: str) -> dict | None:
        """Enrich an organization by domain.

        Returns a normalized dict with any subset of:
          headcount, founded_year, description, industry, phone.
        Returns None if Apollo is disabled, the org wasn't found, or any
        error occurs.
        """
        if not self.enabled:
            log.warning("apollo_org_skipped", reason="disabled", domain=domain)
            return None

        data = self._post("/organizations/enrich", {"domain": domain})
        if not data or not data.get("organization"):
            log.info("apollo_org_no_data", domain=domain,
                     top_level_keys=list(data.keys()) if data else None)
            return None

        org = data["organization"]
        result: dict = {}

        if org.get("estimated_num_employees"):
            result["headcount"] = org["estimated_num_employees"]
        if org.get("founded_year"):
            result["founded_year"] = org["founded_year"]
        if org.get("short_description"):
            result["description"] = org["short_description"]
        if org.get("industry"):
            result["industry"] = org["industry"]
        if org.get("phone"):
            result["phone"] = org["phone"]

        if result:
            log.info("apollo_org_enriched", domain=domain, fields=list(result.keys()))
        return result or None


def _extract_domain(url: str) -> str | None:
    try:
        host = urlparse(url).netloc
        return host.removeprefix("www.") or None
    except Exception:
        return None


apollo_client = ApolloClient()
