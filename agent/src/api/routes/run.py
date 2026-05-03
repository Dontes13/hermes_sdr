from fastapi import APIRouter
from pydantic import BaseModel

from agent.src.api.deps import CurrentUser
from agent.src.clients.supabase_client import supabase
from agent.src.functions.draft import draft
from agent.src.functions.enrich import enrich
from agent.src.functions.poll import poll_replies
from agent.src.functions.prospect import prospect

router = APIRouter()


class ProspectBody(BaseModel):
    city: str
    count: int = 5


@router.post("/prospect")
def run_prospect(_user: CurrentUser, body: ProspectBody):
    """Run prospect() for a city."""
    inserted_ids = prospect(body.city, max_leads=body.count)
    return {"inserted_ids": inserted_ids}


@router.post("/enrich-batch")
def run_enrich_batch(_user: CurrentUser):
    """Enrich all leads with status='new', capped at 20."""
    leads_resp = (
        supabase.table("leads")
        .select("id")
        .eq("status", "new")
        .limit(20)
        .execute()
    )

    enriched = 0
    dead = 0
    errors: list[str] = []

    for row in leads_resp.data:
        try:
            result = enrich(row["id"])
            if result:
                enriched += 1
            else:
                dead += 1
        except Exception as e:
            errors.append(f"{row['id']}: {e}")

    return {"enriched": enriched, "dead": dead, "errors": errors}


@router.post("/draft-batch")
def run_draft_batch(_user: CurrentUser):
    """Draft emails for all leads with status='enriched', capped at 20."""
    leads_resp = (
        supabase.table("leads")
        .select("id")
        .eq("status", "enriched")
        .limit(20)
        .execute()
    )

    drafted = 0
    errors: list[str] = []

    for row in leads_resp.data:
        try:
            draft(row["id"])
            drafted += 1
        except Exception as e:
            errors.append(f"{row['id']}: {e}")

    return {"drafted": drafted, "errors": errors}


@router.post("/poll-replies")
def trigger_poll_replies(_user: CurrentUser):
    """Manually trigger the reply poller. Returns the summary dict."""
    return poll_replies()
