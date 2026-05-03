TIER_NAMES = {
    1: "Brand/Slogan",
    2: "Website Intel",
    3: "Reputation",
    4: "Market Context",
    5: "Baseline",
}


def compute_available_tiers(lead: dict) -> list[int]:
    """Return sorted ascending list of available hook tiers. Tier 5 always present."""
    intel = lead.get("intel_json") or {}
    tiers = []

    # Tier 1: Brand/Slogan
    if intel.get("slogan") or intel.get("value_prop"):
        tiers.append(1)

    # Tier 2: Website Intel
    if (
        intel.get("year_founded")
        or intel.get("agent_count")
        or intel.get("specialties")
        or intel.get("notable_facts")
    ):
        tiers.append(2)

    # Tier 3: Reputation — explicit None checks to avoid 0/False trap
    rating = lead.get("google_rating")
    reviews = lead.get("google_reviews")
    if (
        rating is not None
        and rating >= 4.5
        and reviews is not None
        and reviews >= 25
    ):
        tiers.append(3)

    # Tier 4: Market Context
    if intel.get("markets_served"):
        tiers.append(4)

    # Tier 5: Baseline (always)
    tiers.append(5)

    return sorted(tiers)
