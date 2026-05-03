from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.src.api.deps import CurrentUser
from agent.src.clients.supabase_client import supabase

router = APIRouter()

ALLOWED_KEYS = {
    "target_cities",
    "calendly_link",
    "sender_name",
    "sender_title",
    "daily_lead_cap",
}


class ConfigBody(BaseModel):
    key: str
    value: str


@router.get("")
def get_config(_user: CurrentUser):
    """Return all config rows as a flat dict."""
    resp = supabase.table("config").select("key, value").execute()
    return {row["key"]: row["value"] for row in resp.data}


@router.post("")
def set_config(_user: CurrentUser, body: ConfigBody):
    """Upsert a config row. Only whitelisted keys allowed."""
    if body.key not in ALLOWED_KEYS:
        raise HTTPException(
            400,
            f"Key '{body.key}' not allowed. "
            f"Allowed keys: {', '.join(sorted(ALLOWED_KEYS))}",
        )

    supabase.table("config").upsert(
        {"key": body.key, "value": body.value}
    ).execute()

    return {"ok": True, "key": body.key, "value": body.value}
