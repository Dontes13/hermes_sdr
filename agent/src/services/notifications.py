import structlog

from agent.src.clients.agentmail import agentmail_client
from agent.src.clients.supabase_client import supabase

log = structlog.get_logger(__name__)

DASHBOARD_URL = "https://hermes-phi-tawny.vercel.app/replies"


def send_reply_notification(message: dict, lead: dict) -> bool:
    """Send a notification email when a new inbound reply is detected.

    Args:
        message: AgentMail message dict (keys: message_id, subject, text, from).
        lead: Lead dict with at least 'company' and 'email'.

    Returns True on success, False on any failure (never raises).
    """
    try:
        config_resp = (
            supabase.table("config")
            .select("value")
            .eq("key", "notify_email")
            .single()
            .execute()
        )
        if not config_resp.data:
            log.error("notify_email_config_missing")
            return False

        notify_email = config_resp.data["value"]
        company = lead.get("company", "Unknown")
        from_email = message.get("from") or lead.get("email") or ""
        subject = message.get("subject") or "(no subject)"
        body_text = message.get("text") or ""
        body_preview = body_text[:500] + ("..." if len(body_text) > 500 else "")
        reply_intent = message.get("reply_intent") or "not classified"

        email_subject = f"New reply from {company} — needs response"
        email_body = (
            f"Hi team,\n\n"
            f"A new reply just came in from {company} and needs a response.\n\n"
            f"From: {from_email}\n"
            f"Company: {company}\n"
            f"Subject: {subject}\n\n"
            f"First lines of their reply:\n"
            f"{body_preview}\n\n"
            f"Reply intent (AI-classified): {reply_intent}\n\n"
            f"Open the dashboard to view the full thread and respond:\n"
            f"{DASHBOARD_URL}\n\n"
            f"— Hermes"
        )

        agentmail_client.send_message(
            to=notify_email,
            subject=email_subject,
            text=email_body,
        )
        log.info(
            "reply_notification_sent",
            to=notify_email,
            company=company,
            from_email=from_email,
        )
        return True

    except Exception as e:
        log.error("reply_notification_failed", error=str(e))
        return False
