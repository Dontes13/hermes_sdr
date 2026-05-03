from pathlib import Path

import structlog
from jinja2 import Template

from agent.src.clients.gemini import gemini
from agent.src.clients.supabase_client import supabase
from agent.src.exceptions import BriefError
from agent.src.functions.knowledge_base import load_knowledge_base

log = structlog.get_logger(__name__)

BRIEF_TEMPLATE = Template(
    (Path(__file__).parent.parent / "prompts" / "brief.j2").read_text()
)


def brief(lead_id: str) -> str:
    """Generate a long-form pre-call briefing markdown for a lead.

    Stores the markdown on lead.briefing_md. Flips status replied → booked
    (leaves other statuses alone). Returns the markdown string.
    """
    # 1. Load lead
    try:
        lead_resp = (
            supabase.table("leads")
            .select("*")
            .eq("id", lead_id)
            .single()
            .execute()
        )
    except Exception as e:
        raise BriefError(f"lead {lead_id} not found: {e}") from e
    lead = lead_resp.data

    # 2. Load full thread
    thread_resp = (
        supabase.table("messages")
        .select("direction, subject, body, sent_at, created_at")
        .eq("lead_id", lead_id)
        .order("created_at", desc=False)
        .execute()
    )
    thread = thread_resp.data

    # 3. Load sender info from config
    config_resp = (
        supabase.table("config")
        .select("key, value")
        .in_("key", ["sender_name", "sender_title"])
        .execute()
    )
    config_map = {row["key"]: row["value"] for row in config_resp.data}
    sender_name = config_map.get("sender_name", "Enrique")
    sender_title = config_map.get("sender_title", "CTO, Helios Marketing")

    # 4. Render prompt
    intel = lead.get("intel_json") or {}
    prompt = BRIEF_TEMPLATE.render(
        lead=lead,
        intel=intel,
        thread=thread,
        sender_name=sender_name,
        sender_title=sender_title,
        knowledge_base=load_knowledge_base(),
    )

    # 5. Call Gemini Flash (text, not JSON)
    try:
        markdown = gemini.generate_text_flash(prompt).strip()
    except Exception as e:
        raise BriefError(f"gemini brief generation failed: {e}") from e

    # 6. Update lead: briefing_md + conditional status flip
    update: dict = {"briefing_md": markdown}
    if lead.get("status") == "replied":
        update["status"] = "booked"

    supabase.table("leads").update(update).eq("id", lead_id).execute()

    log.info(
        "brief_generated",
        lead_id=lead_id,
        company=lead["company"],
        length=len(markdown),
    )

    return markdown
