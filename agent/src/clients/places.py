import time

import requests
import structlog

from agent.src.config import settings
from agent.src.exceptions import PlacesError

log = structlog.get_logger(__name__)

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Places API v1 caps at 20 results per page and 3 pages total (60 results).
# We request with pageToken to walk through all available pages.
_MAX_PAGES = 3
_PAGE_SIZE = 20


def search_text(
    city: str,
    target: str = "real estate brokerage",
    page_size: int = _PAGE_SIZE,
) -> list[dict]:
    """Return places matching "{target} in {city}", paginating to ~60 results.

    Google Places caches results per query; walking all 3 pages gives
    prospect() the deepest candidate pool before its place_id dedup guard
    filters out leads that already exist in Supabase.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,"
            "places.websiteUri,places.nationalPhoneNumber,"
            "places.rating,places.userRatingCount,places.types,"
            "nextPageToken"
        ),
    }

    all_places: list[dict] = []
    page_token: str | None = None

    for page_num in range(_MAX_PAGES):
        body: dict = {
            "textQuery": f"{target} in {city}",
            "pageSize": page_size,
        }
        if page_token:
            body["pageToken"] = page_token

        resp = requests.post(SEARCH_URL, json=body, headers=headers, timeout=15)
        if not resp.ok:
            raise PlacesError(f"Places API error {resp.status_code}: {resp.text}")

        data = resp.json()
        places = data.get("places", [])
        all_places.extend(places)

        page_token = data.get("nextPageToken")
        log.info(
            "places_page_fetched",
            city=city,
            page=page_num + 1,
            returned=len(places),
            has_next=bool(page_token),
        )
        if not page_token:
            break

        # Google recommends a short delay before using the next page token
        # (it can be rejected if used too quickly after issue).
        time.sleep(1.5)

    log.info("places_search_complete", city=city, total=len(all_places))
    return all_places
