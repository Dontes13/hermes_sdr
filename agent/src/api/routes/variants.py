from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.src.api.deps import CurrentUser
from agent.src.clients.supabase_client import supabase

router = APIRouter()


class CreateVariantBody(BaseModel):
    name: str
    subject_prompt: str
    is_active: bool = True


class UpdateVariantBody(BaseModel):
    name: str | None = None
    subject_prompt: str | None = None
    is_active: bool | None = None


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
