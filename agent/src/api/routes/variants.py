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
