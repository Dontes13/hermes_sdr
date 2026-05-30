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
from agent.src.exceptions import ApolloError

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

    @staticmethod
    def _log_rate_limit_headers(path: str, resp: "requests.Response") -> None:
        """Surface Apollo's remaining rate-limit budget for observability.

        Apollo returns several headers (names vary by plan/endpoint, e.g.
        x-rate-limit-*, x-minute-requests-left). We log whatever is present
        rather than hardcoding a 1 req/s assumption.
        """
        keys = [
            k for k in resp.headers
            if k.lower().startswith("x-rate-limit")
            or k.lower().endswith("requests-left")
        ]
        if keys:
            log.info(
                "apollo_rate_limit",
                path=path,
                headers={k: resp.headers[k] for k in keys},
            )

    @staticmethod
    def _retry_after_seconds(resp: "requests.Response", attempt: int) -> float:
        """Seconds to wait before retrying a 429. Honors Retry-After when
        present, else exponential backoff (2, 4, 8, …) capped at 30s."""
        ra = resp.headers.get("Retry-After")
        if ra:
            try:
                return min(float(ra), 60.0)
            except ValueError:
                pass
        return min(2.0 ** (attempt + 1), 30.0)

    def _request_with_retry(
        self, path: str, payload: dict, *, max_retries: int = 3
    ) -> dict | None:
        """POST to Apollo with 429 backoff for the sourcing path.

        Unlike _post() (used by the enrichment pipeline, which intentionally
        abandons on 429 so a best-effort enrich never blocks), this retries:
        sourcing must not silently drop a search page or a paid reveal. A 429
        means the request was rejected before processing, so retrying it does
        not double-spend a credit.

        Returns parsed JSON on success. Raises ApolloError (carrying the
        upstream status) on any terminal failure — the sourcing path surfaces
        it rather than swallowing it into an empty result.
        """
        if not self._api_key:
            log.warning("apollo_disabled", reason="no_api_key")
            raise ApolloError("Apollo is not configured (no API key)", 503)

        safe_payload = {k: v for k, v in payload.items() if k != "api_key"}
        attempt = 0
        while True:
            self._throttle()
            log.info(
                "apollo_call_start", path=path, payload=safe_payload, attempt=attempt
            )
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
                log.warning(
                    "apollo_request_failed", path=path, error=str(exc), attempt=attempt
                )
                raise ApolloError(f"Apollo request failed: {exc}", 0) from exc

            self._log_rate_limit_headers(path, resp)

            if resp.status_code == 429:
                if attempt >= max_retries:
                    log.warning(
                        "apollo_rate_limited_exhausted", path=path, attempt=attempt
                    )
                    raise ApolloError("Apollo rate limit exceeded", 429)
                wait = self._retry_after_seconds(resp, attempt)
                log.warning(
                    "apollo_rate_limited_retry",
                    path=path,
                    attempt=attempt,
                    wait_s=wait,
                )
                time.sleep(wait)
                attempt += 1
                continue

            if not resp.ok:
                log.warning(
                    "apollo_api_error",
                    path=path,
                    status=resp.status_code,
                    body_snippet=resp.text[:300],
                )
                raise ApolloError(
                    f"Apollo API error {resp.status_code}: {resp.text[:300]}",
                    resp.status_code,
                )

            try:
                return resp.json()
            except Exception as exc:
                log.warning("apollo_parse_error", path=path, error=str(exc))
                raise ApolloError(f"Apollo response parse error: {exc}", resp.status_code) from exc

    def people_search(
        self, *, page: int = 1, per_page: int = 25, **filters
    ) -> dict | None:
        """POST /people/search. No credits spent — emails come back LOCKED.

        `filters` are passed through as Apollo search params (e.g.
        person_titles, person_locations, q_keywords). Returns the raw Apollo
        response ({"people": [...], "pagination": {...}, ...}) or None.
        """
        per_page = max(1, min(per_page, 100))
        payload = {"page": max(1, page), "per_page": per_page, **filters}
        return self._request_with_retry("/people/search", payload)

    def mixed_people_search(
        self, *, page: int = 1, per_page: int = 25, **filters
    ) -> dict | None:
        """POST /mixed_people/search. No credits spent — emails LOCKED.

        Returns both net-new `people` and already-in-account `contacts`
        arrays plus `pagination`. Returns the raw response or None.
        """
        per_page = max(1, min(per_page, 100))
        payload = {"page": max(1, page), "per_page": per_page, **filters}
        return self._request_with_retry("/mixed_people/search", payload)

    def reveal_person_by_id(
        self, apollo_id: str, *, reveal_personal_emails: bool = False
    ) -> dict | None:
        """Reveal (unlock) one person via /people/match by Apollo person id.

        COSTS ONE CREDIT per call (even when no email is found). Returns the
        raw `person` dict (with the unlocked `email`) or None if the match
        returned nothing or the call failed. Per-id failures return None
        (caught here) so a bulk reveal loop degrades to per-id skips rather
        than aborting the whole batch.
        """
        try:
            data = self._request_with_retry(
                "/people/match",
                {"id": apollo_id, "reveal_personal_emails": reveal_personal_emails},
            )
        except ApolloError as exc:
            log.warning(
                "apollo_reveal_failed",
                apollo_id=apollo_id,
                status=exc.status_code,
                error=str(exc),
            )
            return None
        if not data or not data.get("person"):
            log.info(
                "apollo_reveal_no_person",
                apollo_id=apollo_id,
                top_level_keys=list(data.keys()) if data else None,
            )
            return None
        return data["person"]

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
