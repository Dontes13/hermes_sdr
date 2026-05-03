"""Chat assistant.

Uses Gemini with structured JSON output to decide on each turn whether to
call a tool or reply to the user. Write tools (see chat_tools.REQUIRES_CONFIRMATION)
don't execute immediately; instead the assistant proposes a pending_action
that the UI renders from the tool args. The user confirms or cancels.

History is capped at HISTORY_TURN_CAP turns (user + assistant + tool rounds
count as one turn each). Older turns collapse into a single summary string
so we never silently drop context under token pressure.
"""

import json
import uuid
from typing import Literal

import structlog
from pydantic import BaseModel

from agent.src.clients.gemini import gemini
from agent.src.clients.supabase_client import supabase
from agent.src.functions.chat_tools import (
    REQUIRES_CONFIRMATION,
    TOOL_SCHEMAS,
    execute_tool,
    now_iso,
    tool_arg_schemas_text,
)

log = structlog.get_logger(__name__)

HISTORY_TURN_CAP = 20
MAX_TOOL_LOOPS = 5  # per user message

SYSTEM_PROMPT = f"""You are Hermes Assistant, a helpful operator interface for a real-estate outbound SDR system.

You can call tools to answer questions about the system's data (leads, campaigns, metrics) and to propose actions like creating campaigns.

AVAILABLE TOOLS:
{tool_arg_schemas_text()}

Rules:
- For WRITE tools (marked [WRITE — requires confirmation]): only call them once you have ALL the information the user wants. If any significant field is unspecified, do NOT default it silently — ask the user clarifying questions in a reply first.
  * For create_campaign, confirm with the user on each of these before proposing the tool: name, city, target, autonomy (full vs review_drafts), daily_send_cap, total_lead_cap (or unlimited), sample_email (or none).
  * Gather info across MULTIPLE turns if needed. Users often reply partially — one answer at a time, or corrections later ("actually make it 20/day"). You MUST:
      1. Track what has been answered so far by re-reading the ENTIRE visible conversation (including earlier user turns and the [SUMMARY] if present).
      2. On each turn, list only the fields that are STILL missing, and ask about those — never re-ask what they already answered.
      3. Accept partial answers gracefully. If the user only answers some questions, acknowledge what you got and ask about what remains.
      4. Allow corrections. If the user later changes a value (e.g. "make the cap 20 instead of 10"), update your mental state and reflect the new value in the eventual tool call.
      5. If the user explicitly says "go ahead", "defaults are fine", "just do it", "you pick", or similar, proceed with sensible defaults (autonomy=full, daily_send_cap=15, total_lead_cap=null, sample_email=null) — but ONLY after they've explicitly deferred. Default-picking on your own initiative is forbidden.
  * Only emit the pending action once every required field has been explicitly confirmed or the user has explicitly deferred.
  * Ask up to ~3 questions per turn — more than that overwhelms. If more are needed, gather in waves.
  * The UI handles the final confirm step — do NOT ask the user to confirm again in your reply before emitting the tool call.
- For READ tools: call them freely to gather data. Loop tool → reply as needed.
- Keep replies concise. Numbers are more useful than adjectives.
- QUOTE tool fields VERBATIM. Do NOT sum, derive, or infer numbers that the tool didn't explicitly return. If you need a metric that isn't in the result, say so or call another tool.
- Use the exact field names from the tool result. For example, use `emails_sent_total` and `response_rate` directly from get_stats; do NOT add up status buckets to estimate sends.
- If the user asks for a definition, read the `_notes` field of the tool result if present and quote it.
- Never make up data. If a tool returns an error or empty result, say so.
- When composing a campaign target, prefer the user's exact words ("small coffee shops", "boutique law firms").

On every turn, respond ONLY with JSON of shape:
  {{"action": "reply", "reply": "..."}} — send a final message to the user
  {{"action": "tool",  "tool_name": "...", "tool_args_json": "{{\\"city\\": \\"Miami\\"}}"}} — call a tool

tool_args_json MUST be a JSON-encoded string of the arg object (not a nested
object). Escape quotes as needed. Example: tool_args_json = "{{\\"city\\": \\"Austin\\", \\"daily_send_cap\\": 5}}".

No other output. No prose outside the JSON.
"""


class AssistantDecision(BaseModel):
    action: Literal["reply", "tool"]
    reply: str | None = None
    tool_name: str | None = None
    # JSON-encoded string (Gemini's response_schema doesn't allow open-ended
    # dict / additionalProperties). Parsed server-side before dispatch.
    tool_args_json: str | None = None


# ---------------------------------------------------------------------------
# Session storage
# ---------------------------------------------------------------------------


def _gc_empty_sessions() -> None:
    """Delete any session that has no messages. Called before creating a new
    session so abandoned empties don't accumulate in history."""
    resp = (
        supabase.table("chat_sessions")
        .select("id, messages")
        .execute()
    )
    to_delete = [r["id"] for r in resp.data if not (r.get("messages") or [])]
    if to_delete:
        supabase.table("chat_sessions").delete().in_("id", to_delete).execute()


def create_session() -> dict:
    _gc_empty_sessions()
    resp = (
        supabase.table("chat_sessions")
        .insert({"messages": [], "pending_action": None})
        .execute()
    )
    return resp.data[0]


def list_sessions(limit: int = 50) -> list[dict]:
    """Return recent NON-EMPTY sessions with a preview derived from the first
    user message. Empty sessions are not shown in history."""
    resp = (
        supabase.table("chat_sessions")
        .select("id, messages, pending_action, created_at, updated_at")
        .order("updated_at", desc=True)
        .limit(limit * 2)  # overfetch because we'll filter empties
        .execute()
    )
    out = []
    for row in resp.data:
        messages: list[dict] = row.get("messages") or []
        # Skip sessions with no user-visible content
        has_content = any(
            m.get("role") in ("user", "assistant") for m in messages
        )
        if not has_content:
            continue
        first_user = next(
            (m.get("content", "") for m in messages if m.get("role") == "user"),
            "",
        )
        preview = (first_user or "New chat").strip()
        if len(preview) > 80:
            preview = preview[:77] + "…"
        out.append(
            {
                "id": row["id"],
                "preview": preview,
                "message_count": len(messages),
                "has_pending": bool(row.get("pending_action")),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        if len(out) >= limit:
            break
    return out


def delete_session(session_id: str) -> None:
    supabase.table("chat_sessions").delete().eq("id", session_id).execute()


def load_session(session_id: str) -> dict | None:
    resp = supabase.table("chat_sessions").select("*").eq("id", session_id).execute()
    return resp.data[0] if resp.data else None


def _save_session(session_id: str, messages: list[dict], pending_action: dict | None) -> None:
    supabase.table("chat_sessions").update(
        {"messages": messages, "pending_action": pending_action}
    ).eq("id", session_id).execute()


# ---------------------------------------------------------------------------
# History management
# ---------------------------------------------------------------------------


def _cap_history(messages: list[dict]) -> list[dict]:
    """Keep the last HISTORY_TURN_CAP turns. Collapse older ones into a
    single 'summary' system entry so context survives but tokens don't
    explode."""
    if len(messages) <= HISTORY_TURN_CAP:
        return messages
    overflow = messages[: -HISTORY_TURN_CAP]
    keep = messages[-HISTORY_TURN_CAP:]
    summary_lines = []
    for m in overflow:
        role = m.get("role", "?")
        if role == "user":
            summary_lines.append(f"user: {m.get('content', '')[:120]}")
        elif role == "assistant":
            summary_lines.append(f"assistant: {m.get('content', '')[:120]}")
        elif role == "tool":
            summary_lines.append(f"tool {m.get('name', '?')} -> ok")
    summary = {
        "role": "summary",
        "content": "Earlier turns (summarized):\n" + "\n".join(summary_lines),
    }
    return [summary, *keep]


def _render_prompt(messages: list[dict]) -> str:
    """Serialize the capped history into a single prompt string."""
    lines = [SYSTEM_PROMPT, ""]
    for m in messages:
        role = m["role"]
        if role == "summary":
            lines.append(f"[SUMMARY]\n{m['content']}\n")
        elif role == "user":
            lines.append(f"USER: {m['content']}")
        elif role == "assistant":
            lines.append(f"ASSISTANT: {m['content']}")
        elif role == "tool":
            lines.append(
                f"TOOL RESULT ({m['name']}):\n{json.dumps(m['result'])[:2000]}"
            )
        elif role == "system":
            lines.append(f"[SYSTEM] {m['content']}")
    lines.append("")
    lines.append("Respond with ONLY the JSON decision object.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def send_message(session_id: str, user_message: str) -> dict:
    """Append a user message, drive the tool loop, return {reply, pending_action?}."""
    session = load_session(session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")

    messages: list[dict] = session.get("messages") or []
    prior_pending = session.get("pending_action")

    # If a pending action was sitting around, a new user message cancels it.
    if prior_pending:
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Previous pending action ({prior_pending.get('tool_name')}) "
                    "was cancelled because you sent a new message."
                ),
            }
        )

    messages.append({"role": "user", "content": user_message, "at": now_iso()})

    pending_action: dict | None = None
    final_reply: str | None = None

    for loop_ix in range(MAX_TOOL_LOOPS):
        messages = _cap_history(messages)
        prompt = _render_prompt(messages)
        decision: AssistantDecision = gemini.generate_json_pro(prompt, AssistantDecision)

        if decision.action == "reply":
            final_reply = decision.reply or ""
            messages.append(
                {"role": "assistant", "content": final_reply, "at": now_iso()}
            )
            break

        # tool path
        tool_name = decision.tool_name or ""
        tool_args: dict = {}
        if decision.tool_args_json:
            try:
                parsed_args = json.loads(decision.tool_args_json)
                if isinstance(parsed_args, dict):
                    tool_args = parsed_args
                else:
                    messages.append(
                        {
                            "role": "tool",
                            "name": tool_name or "(missing)",
                            "result": {
                                "error": "tool_args_json must decode to an object"
                            },
                        }
                    )
                    continue
            except json.JSONDecodeError as e:
                messages.append(
                    {
                        "role": "tool",
                        "name": tool_name or "(missing)",
                        "result": {"error": f"tool_args_json not valid JSON: {e}"},
                    }
                )
                continue

        if tool_name not in TOOL_SCHEMAS:
            messages.append(
                {
                    "role": "tool",
                    "name": tool_name or "(missing)",
                    "result": {"error": f"Unknown tool: {tool_name}"},
                }
            )
            continue

        if tool_name in REQUIRES_CONFIRMATION:
            # Validate args before surfacing the confirm card so the UI renders
            # from validated structured args, not model prose.
            args_cls = TOOL_SCHEMAS[tool_name]["args"]
            try:
                validated = args_cls.model_validate(tool_args)
                tool_args_clean = validated.model_dump()
            except Exception as e:
                messages.append(
                    {
                        "role": "tool",
                        "name": tool_name,
                        "result": {"error": f"Invalid args: {e}"},
                    }
                )
                continue
            pending_action = {
                "action_id": str(uuid.uuid4()),
                "tool_name": tool_name,
                "tool_args": tool_args_clean,
                "created_at": now_iso(),
            }
            final_reply = (
                decision.reply
                or f"I'd like to run {tool_name}. Review the details and confirm when ready."
            )
            messages.append(
                {"role": "assistant", "content": final_reply, "at": now_iso()}
            )
            break

        # Read-only tool: execute and loop
        result = execute_tool(tool_name, tool_args)
        messages.append({"role": "tool", "name": tool_name, "result": result})
    else:
        final_reply = (
            "I hit a tool-use loop limit. Try rephrasing your question — "
            "I may be stuck calling tools in a circle."
        )
        messages.append(
            {"role": "assistant", "content": final_reply, "at": now_iso()}
        )

    _save_session(session_id, messages, pending_action)
    log.info(
        "chat_message_handled",
        session_id=session_id,
        loops=loop_ix + 1,
        pending=bool(pending_action),
    )
    return {
        "reply": final_reply or "",
        "pending_action": pending_action,
        "messages": messages,
    }


def confirm_action(
    session_id: str,
    action_id: str,
    tool_args_override: dict | None = None,
) -> dict:
    """Execute the pending action if action_id matches. Appends result to
    history. If `tool_args_override` is passed, validate it against the
    tool's Pydantic schema and use those args instead — lets the UI support
    inline edits to the confirm card.
    """
    session = load_session(session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")
    pending = session.get("pending_action")
    if not pending:
        raise ValueError("No pending action for this session")
    if pending.get("action_id") != action_id:
        raise ValueError("action_id mismatch; pending action may have been replaced")

    messages: list[dict] = session.get("messages") or []
    tool_name = pending["tool_name"]
    tool_args = pending["tool_args"]

    if tool_args_override is not None:
        # Validate user edits against the tool's arg schema before touching
        # production code paths. Invalid edits surface a clear 400 to the UI.
        if tool_name not in TOOL_SCHEMAS:
            raise ValueError(f"Unknown tool: {tool_name}")
        args_cls = TOOL_SCHEMAS[tool_name]["args"]
        try:
            validated = args_cls.model_validate(tool_args_override)
        except Exception as e:
            raise ValueError(f"Invalid edits: {e}") from e
        tool_args = validated.model_dump()

    result = execute_tool(tool_name, tool_args)
    messages.append(
        {
            "role": "system",
            "content": f"User confirmed {tool_name}.",
        }
    )
    messages.append({"role": "tool", "name": tool_name, "result": result})

    # Drive one more model call so the assistant can summarize the outcome.
    messages = _cap_history(messages)
    prompt = _render_prompt(messages)
    decision: AssistantDecision = gemini.generate_json_pro(prompt, AssistantDecision)

    reply = (
        decision.reply
        if decision.action == "reply" and decision.reply
        else f"{tool_name} completed."
    )
    messages.append({"role": "assistant", "content": reply, "at": now_iso()})

    _save_session(session_id, messages, None)
    log.info(
        "chat_action_confirmed",
        session_id=session_id,
        tool_name=tool_name,
        had_error="error" in (result or {}),
    )
    return {"reply": reply, "result": result, "messages": messages}


def cancel_pending(session_id: str) -> dict:
    """Clear the pending action without executing."""
    session = load_session(session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")
    pending = session.get("pending_action")
    if not pending:
        return {"ok": True, "had_pending": False}
    messages: list[dict] = session.get("messages") or []
    messages.append(
        {
            "role": "system",
            "content": f"User cancelled pending {pending.get('tool_name')}.",
        }
    )
    _save_session(session_id, messages, None)
    return {"ok": True, "had_pending": True}
