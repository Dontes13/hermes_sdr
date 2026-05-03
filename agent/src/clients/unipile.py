"""Unipile client — LinkedIn messaging provider.

Unipile exposes a REST API over a per-tenant DSN (e.g. api3.unipile.com:13344).
We use it for three things:

  1. Send connection invitations (with a short note).
  2. Send DMs in an existing chat (only after the invite is accepted).
  3. Pull invite status updates + inbound DMs for the reply loop.

The surface mirrors `agentmail.py` so the rest of the codebase can treat
LinkedIn as a parallel channel (channel='linkedin_invite' | 'linkedin_dm'
on the messages table) without caring about provider differences.

Endpoint paths follow Unipile's documented v1 API. If your tenant is on a
different version, override the paths via the constants below.
"""

from datetime import datetime
from typing import Optional

import requests
import structlog

from agent.src.config import settings
from agent.src.exceptions import UnipileError
from agent.src.utils.retry import retry_network

log = structlog.get_logger(__name__)

# Path constants — kept at module scope so a tenant on a different API
# version can monkeypatch in one place.
INVITE_PATH = "/api/v1/users/invite"
INVITE_LIST_PATH = "/api/v1/users/invite/sent"
CHATS_PATH = "/api/v1/chats"
CHAT_MESSAGES_PATH = "/api/v1/chats/{chat_id}/messages"

# LinkedIn's hard cap on the connection-request note. Enforced server-side
# by LinkedIn — exceeding it causes Unipile to return 4xx, so we validate
# in the drafter and again here as a safety net.
INVITE_NOTE_MAX_CHARS = 280


class UnipileClient:
    def __init__(self) -> None:
        self._session = requests.Session()
        if settings.UNIPILE_API_KEY:
            self._session.headers.update(
                {
                    "X-API-KEY": settings.UNIPILE_API_KEY,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            )

    @property
    def enabled(self) -> bool:
        return bool(
            settings.UNIPILE_API_KEY
            and settings.UNIPILE_DSN
            and settings.UNIPILE_ACCOUNT_ID
        )

    def _url(self, path: str) -> str:
        if not settings.UNIPILE_DSN:
            raise UnipileError("UNIPILE_DSN is not configured")
        # DSN may or may not include scheme; normalize to https.
        dsn = settings.UNIPILE_DSN
        if not dsn.startswith(("http://", "https://")):
            dsn = f"https://{dsn}"
        return f"{dsn.rstrip('/')}{path}"

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise UnipileError(
                "Unipile is not configured. Set UNIPILE_API_KEY, UNIPILE_DSN, "
                "and UNIPILE_ACCOUNT_ID in .env."
            )

    @retry_network(extra_exceptions=(UnipileError,))
    def send_invite(self, linkedin_url: str, note: str) -> dict:
        """Send a connection invitation with a note.

        Returns {'invite_id': str, 'provider_url': str | None}. Raises
        UnipileError on bad input or provider failure.
        """
        self._require_enabled()
        if len(note) > INVITE_NOTE_MAX_CHARS:
            raise UnipileError(
                f"invite note is {len(note)} chars; LinkedIn limit is "
                f"{INVITE_NOTE_MAX_CHARS}"
            )

        payload = {
            "account_id": settings.UNIPILE_ACCOUNT_ID,
            "provider_id": linkedin_url,  # Unipile resolves URL → provider id
            "message": note,
        }
        try:
            resp = self._session.post(self._url(INVITE_PATH), json=payload, timeout=30)
        except requests.RequestException as e:
            raise UnipileError(f"invite request failed: {e}") from e

        if not resp.ok:
            raise UnipileError(f"invite failed [{resp.status_code}]: {resp.text}")

        body = resp.json() if resp.content else {}
        invite_id = body.get("invite_id") or body.get("id") or ""
        log.info(
            "unipile_invite_sent",
            linkedin_url=linkedin_url,
            invite_id=invite_id,
        )
        return {"invite_id": invite_id, "raw": body}

    @retry_network(extra_exceptions=(UnipileError,))
    def send_message(
        self,
        body: str,
        *,
        chat_id: Optional[str] = None,
        linkedin_url: Optional[str] = None,
    ) -> dict:
        """Send a DM. Either chat_id (existing conversation) or linkedin_url
        (start a new chat) must be provided.

        Returns {'message_id': str, 'chat_id': str}.
        """
        self._require_enabled()
        if not chat_id and not linkedin_url:
            raise UnipileError("send_message requires chat_id or linkedin_url")

        try:
            if chat_id:
                payload = {"text": body}
                url = self._url(CHAT_MESSAGES_PATH.format(chat_id=chat_id))
                resp = self._session.post(url, json=payload, timeout=30)
            else:
                payload = {
                    "account_id": settings.UNIPILE_ACCOUNT_ID,
                    "attendees_ids": [linkedin_url],
                    "text": body,
                }
                resp = self._session.post(
                    self._url(CHATS_PATH), json=payload, timeout=30
                )
        except requests.RequestException as e:
            raise UnipileError(f"message request failed: {e}") from e

        if not resp.ok:
            raise UnipileError(f"message failed [{resp.status_code}]: {resp.text}")

        data = resp.json() if resp.content else {}
        out_chat_id = data.get("chat_id") or chat_id or ""
        msg_id = data.get("message_id") or data.get("id") or ""
        log.info(
            "unipile_message_sent",
            chat_id=out_chat_id,
            message_id=msg_id,
        )
        return {"message_id": msg_id, "chat_id": out_chat_id}

    @retry_network(extra_exceptions=(UnipileError,))
    def list_invite_status_since(self, since_dt: datetime) -> list[dict]:
        """Return invitations whose status changed since since_dt.

        Each item: {invite_id, status: 'pending'|'accepted'|'declined',
        provider_url, updated_at}.
        """
        self._require_enabled()
        params = {
            "account_id": settings.UNIPILE_ACCOUNT_ID,
            "since": since_dt.isoformat(),
        }
        try:
            resp = self._session.get(
                self._url(INVITE_LIST_PATH), params=params, timeout=30
            )
        except requests.RequestException as e:
            raise UnipileError(f"invite list failed: {e}") from e

        if not resp.ok:
            raise UnipileError(f"invite list failed [{resp.status_code}]: {resp.text}")

        items = (resp.json() or {}).get("items", [])
        out: list[dict] = []
        for it in items:
            out.append(
                {
                    "invite_id": it.get("invite_id") or it.get("id") or "",
                    "status": (it.get("status") or "").lower(),
                    "provider_url": it.get("provider_url") or it.get("recipient_url"),
                    "updated_at": it.get("updated_at") or it.get("status_updated_at"),
                }
            )
        return out

    @retry_network(extra_exceptions=(UnipileError,))
    def list_inbound_since(self, since_dt: datetime) -> list[dict]:
        """Return inbound DMs since since_dt across all chats for our account.

        Each item: {message_id, chat_id, sender_url, body, sent_at}.
        Two-call pattern (list chats → list new messages per chat) mirrors
        AgentMail's list+get.
        """
        self._require_enabled()
        params = {
            "account_id": settings.UNIPILE_ACCOUNT_ID,
            "since": since_dt.isoformat(),
        }
        try:
            chats_resp = self._session.get(
                self._url(CHATS_PATH), params=params, timeout=30
            )
        except requests.RequestException as e:
            raise UnipileError(f"chats list failed: {e}") from e

        if not chats_resp.ok:
            raise UnipileError(
                f"chats list failed [{chats_resp.status_code}]: {chats_resp.text}"
            )

        chats = (chats_resp.json() or {}).get("items", [])
        results: list[dict] = []
        for chat in chats:
            chat_id = chat.get("id") or chat.get("chat_id")
            if not chat_id:
                continue
            try:
                msgs_resp = self._session.get(
                    self._url(CHAT_MESSAGES_PATH.format(chat_id=chat_id)),
                    params={"since": since_dt.isoformat()},
                    timeout=30,
                )
            except requests.RequestException as e:
                log.warning("unipile_chat_messages_failed", chat_id=chat_id, error=str(e))
                continue
            if not msgs_resp.ok:
                continue
            for m in (msgs_resp.json() or {}).get("items", []):
                # Skip our own outbound — only inbound interests the reply loop.
                if m.get("is_sender") or m.get("direction") == "outbound":
                    continue
                results.append(
                    {
                        "message_id": m.get("id") or m.get("message_id") or "",
                        "chat_id": chat_id,
                        "sender_url": m.get("sender_url")
                        or (chat.get("attendee") or {}).get("provider_url"),
                        "body": m.get("text") or "",
                        "sent_at": m.get("timestamp") or m.get("sent_at"),
                    }
                )
        return results


unipile_client = UnipileClient()
