"""Tools the chat assistant can call.

Each tool is a thin wrapper over existing functions / DB queries so the
assistant shares code paths with the UI. Arg schemas are Pydantic models;
the chat layer validates incoming arguments against these before dispatch.
"""

from datetime import datetime, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from agent.src.clients.supabase_client import supabase


# ---------------------------------------------------------------------------
# Read-only tool arg schemas
# ---------------------------------------------------------------------------


class GetStatsArgs(BaseModel):
    pass


class GetCampaignMetricsArgs(BaseModel):
    campaign_id: str


class GetCityMetricsArgs(BaseModel):
    city: str


class ListLeadsArgs(BaseModel):
    status: str | None = None
    city: str | None = None
    campaign_id: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class GetLeadArgs(BaseModel):
    lead_id: str


class ListCampaignsArgs(BaseModel):
    status: str | None = None


# ---------------------------------------------------------------------------
# Write tool arg schemas
# ---------------------------------------------------------------------------


class CreateCampaignArgs(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=200)
    sample_email: str | None = None
    autonomy: Literal["full", "review_drafts"] = "full"
    daily_send_cap: int = Field(default=15, ge=1, le=500)
    total_lead_cap: int | None = Field(default=None, ge=1, le=5000)


class UpdateCampaignStatusArgs(BaseModel):
    campaign_id: str
    status: Literal["active", "paused", "archived"]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


REQUIRES_CONFIRMATION: set[str] = {"create_campaign", "update_campaign_status"}


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_stats": {
        "description": "Overall pipeline stats: lead status counts, hook-tier breakdown of sent emails, last poll time, and pending reply drafts.",
        "args": GetStatsArgs,
    },
    "get_campaign_metrics": {
        "description": "Detailed metrics for a specific campaign: leads, sends, replies, bookings, and rates.",
        "args": GetCampaignMetricsArgs,
    },
    "get_city_metrics": {
        "description": "Aggregate conversion metrics for a city across all campaigns and leads.",
        "args": GetCityMetricsArgs,
    },
    "list_leads": {
        "description": "List leads with optional filters (status, city, campaign_id). Returns summary rows.",
        "args": ListLeadsArgs,
    },
    "get_lead": {
        "description": "Full detail for a single lead by id.",
        "args": GetLeadArgs,
    },
    "list_campaigns": {
        "description": "List all campaigns with their status and metrics.",
        "args": ListCampaignsArgs,
    },
    "create_campaign": {
        "description": "Create a new autonomous campaign. REQUIRES user confirmation before execution.",
        "args": CreateCampaignArgs,
    },
    "update_campaign_status": {
        "description": "Pause, resume, or archive a campaign. REQUIRES user confirmation.",
        "args": UpdateCampaignStatusArgs,
    },
}


def tool_arg_schemas_text() -> str:
    """Human-readable tool list for the system prompt."""
    lines = []
    for name, spec in TOOL_SCHEMAS.items():
        args_cls: type[BaseModel] = spec["args"]
        schema = args_cls.model_json_schema()
        props = schema.get("properties", {}) or {}
        arg_lines = []
        for arg_name, arg_spec in props.items():
            required = arg_name in schema.get("required", [])
            type_str = arg_spec.get("type") or arg_spec.get("anyOf", "?")
            arg_lines.append(
                f"    - {arg_name} ({type_str}){'*' if required else ''}"
            )
        args_block = "\n".join(arg_lines) if arg_lines else "    (no args)"
        confirm = " [WRITE — requires confirmation]" if name in REQUIRES_CONFIRMATION else ""
        lines.append(f"- {name}{confirm}: {spec['description']}\n{args_block}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Read tool implementations
# ---------------------------------------------------------------------------


def _tool_get_stats(_: GetStatsArgs) -> dict:
    """Return unambiguous, explicitly-labeled pipeline stats.

    Each field is defined precisely so the model doesn't have to derive
    numbers from status counts and get them wrong (e.g. summing 'dead' into
    'emails sent').
    """
    counts = {
        s: 0
        for s in (
            "new",
            "enriched",
            "drafted",
            "sent",
            "replied",
            "booked",
            "dead",
            "unsubscribed",
        )
    }
    leads_resp = supabase.table("leads").select("status").execute()
    for row in leads_resp.data:
        if row["status"] in counts:
            counts[row["status"]] += 1
    leads_total = sum(counts.values())

    # Real send count = outbound messages that actually left the system.
    # Status=sent excludes replied/booked/unsubscribed leads that were sent
    # but then moved forward, so count via messages instead.
    sent_resp = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("direction", "outbound")
        .not_.is_("sent_at", "null")
        .execute()
    )
    emails_sent_total = sent_resp.count or 0

    # Fresh cold sends only (excludes replies we sent back).
    cold_sent_resp = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("direction", "outbound")
        .not_.is_("sent_at", "null")
        .not_.is_("hook_tier_used", "null")
        .execute()
    )
    cold_emails_sent = cold_sent_resp.count or 0

    inbound_resp = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("direction", "inbound")
        .execute()
    )
    inbound_total = inbound_resp.count or 0

    replied_leads = counts["replied"] + counts["booked"]
    booked_leads = counts["booked"]
    unsubscribed_leads = counts["unsubscribed"]

    response_rate = (
        round(replied_leads / cold_emails_sent, 4) if cold_emails_sent else 0.0
    )
    book_rate = (
        round(booked_leads / cold_emails_sent, 4) if cold_emails_sent else 0.0
    )

    return {
        "leads_total": leads_total,
        "leads_by_status": counts,
        "emails_sent_total": emails_sent_total,
        "cold_emails_sent": cold_emails_sent,
        "inbound_messages_total": inbound_total,
        "replied_leads": replied_leads,
        "booked_leads": booked_leads,
        "unsubscribed_leads": unsubscribed_leads,
        "response_rate": response_rate,
        "book_rate": book_rate,
        "_notes": (
            "response_rate = replied_leads / cold_emails_sent. "
            "emails_sent_total includes reply drafts we sent back. "
            "cold_emails_sent is the denominator for funnel conversion."
        ),
    }


def _tool_get_campaign_metrics(args: GetCampaignMetricsArgs) -> dict:
    from agent.src.api.routes.campaigns import _campaign_metrics

    camp = (
        supabase.table("campaigns")
        .select("id, name, city, target, status, autonomy, daily_send_cap, total_lead_cap")
        .eq("id", args.campaign_id)
        .execute()
    )
    if not camp.data:
        return {"error": f"Campaign {args.campaign_id} not found"}
    c = camp.data[0]
    c["metrics"] = _campaign_metrics(args.campaign_id)
    return c


def _tool_get_city_metrics(args: GetCityMetricsArgs) -> dict:
    leads_resp = (
        supabase.table("leads")
        .select("id, status")
        .ilike("city", args.city)
        .execute()
    )
    leads = leads_resp.data
    if not leads:
        return {"city": args.city, "leads_total": 0, "note": "no leads in this city"}

    status_counts: dict[str, int] = {}
    for row in leads:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    lead_ids = [r["id"] for r in leads]
    sent_resp = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("direction", "outbound")
        .in_("lead_id", lead_ids)
        .not_.is_("sent_at", "null")
        .execute()
    )
    sent_total = sent_resp.count or 0
    replied = status_counts.get("replied", 0) + status_counts.get("booked", 0)
    booked = status_counts.get("booked", 0)

    return {
        "city": args.city,
        "leads_total": len(leads),
        "status_counts": status_counts,
        "sent_total": sent_total,
        "replied": replied,
        "booked": booked,
        "reply_rate": round(replied / sent_total, 4) if sent_total else 0.0,
        "book_rate": round(booked / sent_total, 4) if sent_total else 0.0,
    }


def _tool_list_leads(args: ListLeadsArgs) -> dict:
    query = (
        supabase.table("leads")
        .select("id, company, city, email, status, google_rating, google_reviews, campaign_id, updated_at")
        .order("updated_at", desc=True)
        .limit(args.limit)
    )
    if args.status:
        query = query.eq("status", args.status)
    if args.city:
        query = query.ilike("city", args.city)
    if args.campaign_id:
        query = query.eq("campaign_id", args.campaign_id)
    resp = query.execute()
    return {"leads": resp.data, "count": len(resp.data)}


def _tool_get_lead(args: GetLeadArgs) -> dict:
    lead = supabase.table("leads").select("*").eq("id", args.lead_id).execute()
    if not lead.data:
        return {"error": f"Lead {args.lead_id} not found"}
    messages = (
        supabase.table("messages")
        .select("id, direction, subject, body, sent_at, created_at, hook_tier_used")
        .eq("lead_id", args.lead_id)
        .order("created_at", desc=False)
        .execute()
    )
    return {"lead": lead.data[0], "messages": messages.data}


def _tool_list_campaigns(args: ListCampaignsArgs) -> dict:
    query = supabase.table("campaigns").select(
        "id, name, city, target, status, autonomy, daily_send_cap, total_lead_cap, created_at"
    ).order("created_at", desc=True)
    if args.status:
        query = query.eq("status", args.status)
    resp = query.execute()
    return {"campaigns": resp.data, "count": len(resp.data)}


# ---------------------------------------------------------------------------
# Write tool implementations (called AFTER user confirmation)
# ---------------------------------------------------------------------------


def _tool_create_campaign(args: CreateCampaignArgs) -> dict:
    from agent.src.api.routes.campaigns import _campaign_metrics

    insert_resp = (
        supabase.table("campaigns")
        .insert(
            {
                "name": args.name,
                "city": args.city,
                "target": args.target,
                "sample_email": args.sample_email,
                "autonomy": args.autonomy,
                "daily_send_cap": args.daily_send_cap,
                "total_lead_cap": args.total_lead_cap,
            }
        )
        .execute()
    )
    campaign = insert_resp.data[0]
    campaign["metrics"] = _campaign_metrics(campaign["id"])
    return campaign


def _tool_update_campaign_status(args: UpdateCampaignStatusArgs) -> dict:
    resp = (
        supabase.table("campaigns")
        .update({"status": args.status})
        .eq("id", args.campaign_id)
        .execute()
    )
    if not resp.data:
        return {"error": f"Campaign {args.campaign_id} not found"}
    return resp.data[0]


TOOL_IMPLEMENTATIONS: dict[str, Callable[[BaseModel], dict]] = {
    "get_stats": _tool_get_stats,
    "get_campaign_metrics": _tool_get_campaign_metrics,
    "get_city_metrics": _tool_get_city_metrics,
    "list_leads": _tool_list_leads,
    "get_lead": _tool_get_lead,
    "list_campaigns": _tool_list_campaigns,
    "create_campaign": _tool_create_campaign,
    "update_campaign_status": _tool_update_campaign_status,
}


def execute_tool(name: str, raw_args: dict) -> dict:
    """Validate args against the registered schema and invoke the tool.

    Returns the tool's dict result, or {"error": str} on validation failure.
    """
    if name not in TOOL_SCHEMAS:
        return {"error": f"Unknown tool: {name}"}
    args_cls: type[BaseModel] = TOOL_SCHEMAS[name]["args"]
    try:
        parsed = args_cls.model_validate(raw_args or {})
    except Exception as e:
        return {"error": f"Invalid args for {name}: {e}"}
    impl = TOOL_IMPLEMENTATIONS[name]
    try:
        return impl(parsed)
    except Exception as e:
        return {"error": f"Tool {name} failed: {e}"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
