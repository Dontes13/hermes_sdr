from pathlib import Path

from fastapi import APIRouter, HTTPException
from jinja2 import Template
from pydantic import BaseModel

from agent.src.api.deps import CurrentUser
from agent.src.clients.gemini import gemini
from agent.src.clients.supabase_client import supabase
from agent.src.exceptions import GeminiError

_SUBJECT_TEMPLATE = Template(
    (Path(__file__).parent.parent.parent / "prompts" / "subject.j2").read_text()
)

_PREVIEW_FAKE_LEAD = {
    "company": "Rosario's Italian Kitchen",
    "city": "Miami",
    "google_rating": 4.5,
    "google_reviews": 127,
    "intel": {
        "slogan": "Authentic Italian, straight from Nonna's kitchen",
        "notable_facts": ["Family-owned since 1998", "Known for handmade pasta"],
    },
    "hook_tier_used": 3,
    "tier_description": "Reputation",
    "hook_text": (
        "You've built a reputation for authentic Italian food in Miami "
        "with 127 five-star reviews"
    ),
}

router = APIRouter()


class CreateVariantBody(BaseModel):
    name: str
    subject_prompt: str
    is_active: bool = True


class UpdateVariantBody(BaseModel):
    name: str | None = None
    subject_prompt: str | None = None
    is_active: bool | None = None


class _SubjectPreviewResult(BaseModel):
    subject: str


@router.get("")
def list_variants(_user: CurrentUser):
    """Return all subject line variants."""
    resp = (
        supabase.table("subject_variants")
        .select("*")
        .order("created_at")
        .execute()
    )
    return resp.data


@router.post("", status_code=201)
def create_variant(_user: CurrentUser, body: CreateVariantBody):
    """Create a new subject line variant."""
    resp = (
        supabase.table("subject_variants")
        .insert(
            {
                "name": body.name.strip(),
                "subject_prompt": body.subject_prompt.strip(),
                "is_active": body.is_active,
            }
        )
        .execute()
    )
    return resp.data[0]


# /stats must be registered before /{variant_id} so FastAPI's router doesn't
# match the literal string "stats" as a path parameter.
@router.get("/stats")
def get_variant_stats(_user: CurrentUser):
    """Per-variant send/reply/booked counts and rates for the A/B Testing tab."""
    variants_resp = (
        supabase.table("subject_variants")
        .select("id,name,is_active")
        .order("created_at")
        .execute()
    )

    result = []
    for v in variants_resp.data:
        vid = v["id"]

        # sends: outbound messages with this variant that have been sent
        sends_resp = (
            supabase.table("messages")
            .select("id", count="exact")
            .eq("subject_variant_id", vid)
            .eq("direction", "outbound")
            .not_.is_("sent_at", "null")
            .execute()
        )
        sends = sends_resp.count or 0

        # lead_ids that received at least one *sent* outbound with this variant
        outbound_resp = (
            supabase.table("messages")
            .select("lead_id")
            .eq("subject_variant_id", vid)
            .eq("direction", "outbound")
            .not_.is_("sent_at", "null")
            .execute()
        )
        lead_ids = list({row["lead_id"] for row in outbound_resp.data})

        replies = 0
        booked = 0
        if lead_ids:
            # replies: how many of those leads have at least one inbound message
            inbound_resp = (
                supabase.table("messages")
                .select("lead_id")
                .eq("direction", "inbound")
                .in_("lead_id", lead_ids)
                .execute()
            )
            replies = len({row["lead_id"] for row in inbound_resp.data})

            # booked: leads with current status = 'booked'.
            # TODO: this doesn't verify the booking happened after the variant's first send
            # to that lead. Acceptable at low volume; revisit when data is meaningful.
            booked_resp = (
                supabase.table("leads")
                .select("id")
                .in_("id", lead_ids)
                .eq("status", "booked")
                .execute()
            )
            booked = len(booked_resp.data)

        reply_rate = round(replies / sends, 4) if sends > 0 else 0.0
        book_rate = round(booked / sends, 4) if sends > 0 else 0.0

        result.append({
            "variant_id": vid,
            "name": v["name"],
            "is_active": v["is_active"],
            "sends": sends,
            "replies": replies,
            "booked": booked,
            "reply_rate": reply_rate,
            "book_rate": book_rate,
        })

    return result


# /{variant_id}/preview must be registered before /{variant_id} so FastAPI
# doesn't swallow "preview" as a variant_id path parameter.
@router.post("/{variant_id}/preview")
def preview_variant(_user: CurrentUser, variant_id: str):
    """Run one subject-line generation against a hardcoded fake lead and return it."""
    variant_resp = (
        supabase.table("subject_variants")
        .select("id, subject_prompt")
        .eq("id", variant_id)
        .limit(1)
        .execute()
    )
    if not variant_resp.data:
        raise HTTPException(404, "Variant not found")
    variant = variant_resp.data[0]

    config_resp = (
        supabase.table("config")
        .select("key, value")
        .in_("key", ["sender_name", "sender_title"])
        .execute()
    )
    config_map = {row["key"]: row["value"] for row in config_resp.data}
    sender_name = config_map.get("sender_name", "Enrique")
    sender_title = config_map.get("sender_title", "CTO, Helios Marketing")

    prompt = _SUBJECT_TEMPLATE.render(
        sender_name=sender_name,
        sender_title=sender_title,
        subject_prompt=variant["subject_prompt"],
        company=_PREVIEW_FAKE_LEAD["company"],
        city=_PREVIEW_FAKE_LEAD["city"],
        google_rating=_PREVIEW_FAKE_LEAD["google_rating"],
        google_reviews=_PREVIEW_FAKE_LEAD["google_reviews"],
        intel=_PREVIEW_FAKE_LEAD["intel"],
        hook_tier_used=_PREVIEW_FAKE_LEAD["hook_tier_used"],
        tier_description=_PREVIEW_FAKE_LEAD["tier_description"],
        hook_text=_PREVIEW_FAKE_LEAD["hook_text"],
    )

    try:
        result = gemini.generate_json_pro(prompt, _SubjectPreviewResult)
    except GeminiError as exc:
        raise HTTPException(502, f"Gemini call failed: {exc}") from exc

    return {"preview": result.subject}


@router.patch("/{variant_id}")
def update_variant(
    _user: CurrentUser, variant_id: str, body: UpdateVariantBody
):
    """Update one or more fields on a variant."""
    patch: dict = {}
    if body.name is not None:
        patch["name"] = body.name.strip()
    if body.subject_prompt is not None:
        patch["subject_prompt"] = body.subject_prompt.strip()
    if body.is_active is not None:
        patch["is_active"] = body.is_active

    if not patch:
        raise HTTPException(400, "No fields to update")

    resp = (
        supabase.table("subject_variants")
        .update(patch)
        .eq("id", variant_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "Variant not found")
    return resp.data[0]


@router.delete("/{variant_id}", status_code=204)
def delete_variant(_user: CurrentUser, variant_id: str):
    """Delete a variant. Past sends using it keep their subject_variant_id FK."""
    resp = (
        supabase.table("subject_variants")
        .delete()
        .eq("id", variant_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "Variant not found")
