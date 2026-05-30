"""Apollo sourcing routes.

Mounted at /api/campaigns (alongside the campaigns router) so the paths read
as /api/campaigns/{id}/apollo/{search,add}. Both routes are JWT-gated.

Two-step credit flow:
  POST /{id}/apollo/search → candidates, emails LOCKED, no credits spent
  POST /{id}/apollo/add    → reveals picked candidates (1 credit each), persists
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent.src.api.deps import CurrentUser
from agent.src.clients.supabase_client import supabase
from agent.src.functions.sourcing import reveal_and_persist, source_leads_from_apollo

router = APIRouter()


class ApolloSearchBody(BaseModel):
    # target/city default to the campaign's own values when omitted.
    target: str | None = None
    city: str | None = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=25, ge=1, le=100)
    use_mixed: bool = True


class ApolloAddBody(BaseModel):
    apollo_person_ids: list[str] = Field(min_length=1, max_length=100)


def _load_campaign(campaign_id: str) -> dict:
    resp = (
        supabase.table("campaigns")
        .select("id, city, target")
        .eq("id", campaign_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "Campaign not found")
    return resp.data[0]


@router.post("/{campaign_id}/apollo/search")
def apollo_search(_user: CurrentUser, campaign_id: str, body: ApolloSearchBody):
    """Search Apollo for candidate leads. No credits spent; emails locked."""
    campaign = _load_campaign(campaign_id)
    target = body.target if body.target is not None else campaign["target"]
    city = body.city if body.city is not None else campaign["city"]
    return source_leads_from_apollo(
        target=target,
        city=city,
        campaign_id=campaign_id,
        limit=body.per_page,
        page=body.page,
        use_mixed=body.use_mixed,
    )


@router.post("/{campaign_id}/apollo/add")
def apollo_add(_user: CurrentUser, campaign_id: str, body: ApolloAddBody):
    """Reveal the picked Apollo people (1 credit each) and persist as leads."""
    _load_campaign(campaign_id)
    return reveal_and_persist(
        apollo_person_ids=body.apollo_person_ids,
        campaign_id=campaign_id,
    )
