from datetime import datetime

import structlog
from agentmail import AgentMail
from agentmail.core.api_error import ApiError
from agentmail.inboxes import CreateInboxRequest

from agent.src.clients.supabase_client import supabase
from agent.src.config import settings
from agent.src.exceptions import AgentMailError
from agent.src.utils.retry import retry_network

log = structlog.get_logger(__name__)

INBOX_CLIENT_ID = "helios-sdr-primary"


class AgentMailClient:
    def __init__(self) -> None:
        self._client = AgentMail(api_key=settings.AGENTMAIL_API_KEY)
        self._inbox_id: str | None = None

    def get_or_create_inbox(self) -> str:
        """Return the inbox_id, creating the inbox if it doesn't exist.

        Lookup order: in-memory cache → agentmail_sync.inbox_id → list existing
        inboxes and match by client_id → create new. The list step handles
        re-runs after the DB cache is cleared (an inbox we created previously
        is still visible under our API key).
        """
        if self._inbox_id:
            return self._inbox_id

        row = (
            supabase.table("agentmail_sync")
            .select("inbox_id")
            .eq("id", 1)
            .single()
            .execute()
        )
        if row.data and row.data.get("inbox_id"):
            self._inbox_id = row.data["inbox_id"]
            return self._inbox_id

        # Check if we already own an inbox with our client_id (handles
        # re-runs after DB cache is cleared but API-side inbox persists).
        try:
            existing = self._client.inboxes.list()
        except ApiError as e:
            raise AgentMailError(f"inbox list failed: {e}") from e

        for inbox in existing.inboxes:
            if inbox.client_id == INBOX_CLIENT_ID:
                self._cache_inbox_id(inbox.inbox_id)
                log.info(
                    "agentmail_inbox_found",
                    inbox_id=inbox.inbox_id,
                    email=inbox.email,
                )
                return inbox.inbox_id

        req_kwargs: dict = {
            "username": settings.AGENTMAIL_INBOX_USERNAME,
            "client_id": INBOX_CLIENT_ID,
        }
        if settings.AGENTMAIL_INBOX_DOMAIN:
            req_kwargs["domain"] = settings.AGENTMAIL_INBOX_DOMAIN

        try:
            inbox = self._client.inboxes.create(
                request=CreateInboxRequest(**req_kwargs)
            )
        except ApiError as e:
            raise AgentMailError(
                f"inbox create failed: {e}. If this is IsTakenError, the "
                f"username '{settings.AGENTMAIL_INBOX_USERNAME}' is claimed "
                f"on the @agentmail.to shared domain — pick a more unique "
                f"AGENTMAIL_INBOX_USERNAME in .env or set "
                f"AGENTMAIL_INBOX_DOMAIN to your own verified domain."
            ) from e

        self._cache_inbox_id(inbox.inbox_id)
        log.info("agentmail_inbox_ready", inbox_id=inbox.inbox_id, email=inbox.email)
        return inbox.inbox_id

    def _cache_inbox_id(self, inbox_id: str) -> None:
        """Persist inbox_id to agentmail_sync and in-memory cache."""
        supabase.table("agentmail_sync").update({"inbox_id": inbox_id}).eq(
            "id", 1
        ).execute()
        self._inbox_id = inbox_id

    @retry_network(extra_exceptions=(ApiError,))
    def send_message(self, to: str, subject: str, text: str) -> dict:
        """Send a new (non-reply) plaintext message.

        Returns {'message_id': str, 'thread_id': str}.
        """
        inbox_id = self.get_or_create_inbox()
        try:
            resp = self._client.inboxes.messages.send(
                inbox_id=inbox_id,
                to=[to],
                subject=subject,
                text=text,
            )
        except ApiError as e:
            raise AgentMailError(f"send failed: {e}") from e

        log.info(
            "agentmail_sent",
            to=to,
            subject=subject,
            message_id=resp.message_id,
            thread_id=resp.thread_id,
        )
        return {"message_id": resp.message_id, "thread_id": resp.thread_id}

    @retry_network(extra_exceptions=(ApiError,))
    def reply_to_message(self, reply_to_message_id: str, text: str) -> dict:
        """Send a reply threaded onto an existing message.

        Threading is handled server-side by AgentMail; no header management
        required. Returns {'message_id': str, 'thread_id': str}.
        """
        inbox_id = self.get_or_create_inbox()
        try:
            resp = self._client.inboxes.messages.reply(
                inbox_id=inbox_id,
                message_id=reply_to_message_id,
                text=text,
            )
        except ApiError as e:
            raise AgentMailError(f"reply failed: {e}") from e

        return {"message_id": resp.message_id, "thread_id": resp.thread_id}

    @retry_network(extra_exceptions=(ApiError,))
    def list_inbound_since(self, since_dt: datetime) -> list[dict]:
        """Fetch inbound messages received since the given datetime.

        Two-call pattern: list() returns MessageItem stubs with preview only,
        then get() fetches the full body per item. Filters server-side to
        the 'received' label to exclude our own sent mail.

        Returns list of dicts with keys: message_id, thread_id, from, subject,
        text, timestamp.
        """
        inbox_id = self.get_or_create_inbox()
        try:
            list_resp = self._client.inboxes.messages.list(
                inbox_id=inbox_id,
                after=since_dt,
                labels=["received"],
            )
        except ApiError as e:
            raise AgentMailError(f"list failed: {e}") from e

        results: list[dict] = []
        for stub in list_resp.messages:
            try:
                full = self._client.inboxes.messages.get(
                    inbox_id=inbox_id,
                    message_id=stub.message_id,
                )
            except ApiError as e:
                log.warning(
                    "agentmail_get_failed",
                    message_id=stub.message_id,
                    error=str(e),
                )
                continue

            results.append(
                {
                    "message_id": full.message_id,
                    "thread_id": full.thread_id,
                    "from": full.from_,
                    "subject": full.subject or "",
                    "text": full.text or "",
                    "extracted_text": full.extracted_text or "",
                    "timestamp": full.timestamp,
                }
            )

        return results


    @retry_network(extra_exceptions=(ApiError,))
    def send_from(self, inbox_id: str, to: str, subject: str, text: str) -> dict:
        """Send a plaintext message from a specific inbox (used by warming).

        Unlike send_message(), this bypasses the get_or_create_inbox() lookup
        and uses the provided inbox_id directly. Returns {'message_id': str,
        'thread_id': str}.
        """
        try:
            resp = self._client.inboxes.messages.send(
                inbox_id=inbox_id,
                to=[to],
                subject=subject,
                text=text,
            )
        except ApiError as e:
            raise AgentMailError(f"send_from failed ({inbox_id}): {e}") from e

        log.info(
            "agentmail_sent_warming",
            from_inbox_id=inbox_id,
            to=to,
            subject=subject,
            message_id=resp.message_id,
            thread_id=resp.thread_id,
        )
        return {"message_id": resp.message_id, "thread_id": resp.thread_id}

    @retry_network(extra_exceptions=(ApiError,))
    def list_inbound_for_inbox(self, inbox_id: str, since_dt: datetime) -> list[dict]:
        """Fetch inbound messages for a specific inbox since a given datetime.

        Used by warming to poll for replies on warming threads without
        touching the main agentmail_sync cursor.
        """
        try:
            list_resp = self._client.inboxes.messages.list(
                inbox_id=inbox_id,
                after=since_dt,
                labels=["received"],
            )
        except ApiError as e:
            raise AgentMailError(f"list_inbound_for_inbox failed ({inbox_id}): {e}") from e

        results: list[dict] = []
        for stub in list_resp.messages:
            try:
                full = self._client.inboxes.messages.get(
                    inbox_id=inbox_id,
                    message_id=stub.message_id,
                )
            except ApiError as e:
                log.warning(
                    "agentmail_warming_get_failed",
                    inbox_id=inbox_id,
                    message_id=stub.message_id,
                    error=str(e),
                )
                continue
            results.append(
                {
                    "message_id": full.message_id,
                    "thread_id": full.thread_id,
                    "from": full.from_,
                    "subject": full.subject or "",
                    "text": full.text or "",
                    "timestamp": full.timestamp,
                }
            )
        return results


agentmail_client = AgentMailClient()
