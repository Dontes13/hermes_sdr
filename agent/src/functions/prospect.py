import structlog

from agent.src.clients.places import search_text
from agent.src.clients.supabase_client import supabase

log = structlog.get_logger(__name__)

DEFAULT_TARGET = "real estate brokerage"


def prospect(
    city: str,
    max_leads: int = 5,
    target: str | None = None,
    campaign_id: str | None = None,
) -> list[str]:
    """Discover leads via Google Places and insert new rows.

    target: free-text audience passed to Places (e.g. "small coffee shops").
    Defaults to real estate brokerages to preserve existing daily-run behavior.
    campaign_id: optional, stamps the lead with its owning campaign.

    Returns list of inserted lead UUIDs in insertion order.
    """
    target_query = target or DEFAULT_TARGET
    results = search_text(city, target=target_query)
    inserted_ids: list[str] = []

    for result in results:
        if len(inserted_ids) >= max_leads:
            break

        place_id = result.get("id")
        if not place_id:
            continue

        # Dedup by place_id in Supabase
        existing = (
            supabase.table("leads")
            .select("id")
            .filter("intel_json->>place_id", "eq", place_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            log.info("prospect_skip_duplicate", place_id=place_id)
            continue

        company = result["displayName"]["text"]
        lead_row: dict = {
            "company": company,
            "city": city,
            "website": result.get("websiteUri"),
            "phone": result.get("nationalPhoneNumber"),
            "google_rating": result.get("rating"),
            "google_reviews": result.get("userRatingCount"),
            "intel_json": {
                "place_id": place_id,
                "address": result.get("formattedAddress"),
                "types": result.get("types", []),
                "target_query": target_query,
            },
            "status": "new",
        }
        if campaign_id:
            lead_row["campaign_id"] = campaign_id

        insert_resp = supabase.table("leads").insert(lead_row).execute()
        lead_id = insert_resp.data[0]["id"]
        inserted_ids.append(lead_id)
        log.info(
            "prospect_inserted",
            company=company,
            lead_id=lead_id,
            campaign_id=campaign_id,
            target=target_query,
        )

    if len(inserted_ids) < max_leads:
        log.warning(
            "prospect_fewer_than_requested",
            requested=max_leads,
            inserted=len(inserted_ids),
            total_results=len(results),
            target=target_query,
        )

    return inserted_ids
