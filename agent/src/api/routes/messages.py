from fastapi import APIRouter, HTTPException

from agent.src.api.deps import CurrentUser
from agent.src.clients.supabase_client import supabase

router = APIRouter()


@router.get("/{message_id}/prompt")
def get_message_prompt(_user: CurrentUser, message_id: str):
    """Return the fully-rendered prompts captured for a draft message.

    404s for drafts created before prompt observability shipped (or for
    LinkedIn/reply drafts, which don't flow through draft.py).
    """
    resp = (
        supabase.table("message_prompts")
        .select("*")
        .eq("message_id", message_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "No prompt captured for this draft")

    row = resp.data[0]

    variant_name = None
    if row.get("subject_variant_id"):
        variant_resp = (
            supabase.table("subject_variants")
            .select("name")
            .eq("id", row["subject_variant_id"])
            .limit(1)
            .execute()
        )
        if variant_resp.data:
            variant_name = variant_resp.data[0]["name"]

    return {
        "body_prompt": row["body_prompt"],
        "subject_prompt": row.get("subject_prompt"),
        "model": row.get("model"),
        "subject_variant_id": row.get("subject_variant_id"),
        "variant_name": variant_name,
        "created_at": row["created_at"],
    }
