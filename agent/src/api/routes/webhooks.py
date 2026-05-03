import hashlib
import hmac
import json

import structlog
from fastapi import APIRouter, HTTPException, Request

from agent.src.clients.supabase_client import supabase
from agent.src.config import settings
from agent.src.exceptions import BriefError
from agent.src.functions.brief import brief

log = structlog.get_logger(__name__)

router = APIRouter()


def _verify_signature(raw_body: bytes, header: str) -> None:
    """Raise HTTPException(400) if the Calendly signature is invalid."""
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        ts = parts["t"]
        sig = parts["v1"]
    except (KeyError, ValueError):
        raise HTTPException(400, "Malformed Calendly-Webhook-Signature header")

    secret = settings.CALENDLY_WEBHOOK_SECRET.encode()
    expected = hmac.new(secret, f"{ts}.{raw_body.decode()}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(400, "Invalid webhook signature")


def _find_lead(email: str) -> dict | None:
    """Return the best-match lead for the given email, or None."""
    resp = (
        supabase.table("leads")
        .select("id, company, status, updated_at")
        .eq("email", email)
        .order("updated_at", desc=True)
        .execute()
    )
    if not resp.data:
        return None

    # Prefer replied > sent > anything else
    priority = {"replied": 0, "sent": 1}
    return sorted(resp.data, key=lambda r: priority.get(r["status"], 2))[0]


@router.post("/calendly")
async def calendly_webhook(request: Request):
    raw_body = await request.body()

    # In prod, signature is required (startup validated the secret exists).
    # In dev, fall through with a warning if the secret isn't configured.
    sig_header = request.headers.get("Calendly-Webhook-Signature", "")
    if settings.APP_ENV == "prod":
        if not sig_header:
            raise HTTPException(401, "Missing Calendly-Webhook-Signature header")
        _verify_signature(raw_body, sig_header)
    elif settings.CALENDLY_WEBHOOK_SECRET:
        _verify_signature(raw_body, sig_header)
    else:
        log.warning("calendly_webhook_unsigned_dev", reason="no secret configured")

    body = json.loads(raw_body)

    if body.get("event") != "invitee.created":
        return {"ok": True, "skipped": True}

    email: str = body.get("payload", {}).get("invitee", {}).get("email", "")
    if not email:
        raise HTTPException(400, "Missing invitee email in payload")

    lead = _find_lead(email)
    if not lead:
        log.warning("calendly_no_lead_match", email=email)
        return {"ok": True, "no_match": True}

    lead_id = lead["id"]

    if lead["status"] == "booked":
        return {"ok": True, "skipped": True, "lead_id": lead_id}

    try:
        brief(lead_id)
    except BriefError as e:
        log.error("calendly_brief_failed", lead_id=lead_id, error=str(e))
        raise HTTPException(500, f"Briefing generation failed: {e}")

    # Ensure status is booked regardless of prior status (brief() only flips replied→booked)
    supabase.table("leads").update({"status": "booked"}).eq("id", lead_id).execute()

    log.info(
        "calendly_booking_received",
        lead_id=lead_id,
        company=lead["company"],
        email=email,
    )
    return {"ok": True, "lead_id": lead_id}
