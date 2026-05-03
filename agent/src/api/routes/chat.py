from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.src.api.deps import CurrentUser
from agent.src.functions.chat import (
    cancel_pending,
    confirm_action,
    create_session,
    delete_session,
    list_sessions,
    load_session,
    send_message,
)

router = APIRouter()


class SendMessageBody(BaseModel):
    message: str


class ConfirmBody(BaseModel):
    action_id: str
    tool_args: dict | None = None


@router.post("/sessions")
def new_session(_user: CurrentUser):
    return create_session()


@router.get("/sessions")
def get_sessions(_user: CurrentUser, limit: int = 50):
    return list_sessions(limit=min(limit, 200))


@router.delete("/{session_id}")
def remove_session(_user: CurrentUser, session_id: str):
    delete_session(session_id)
    return {"ok": True}


@router.get("/{session_id}")
def get_session(_user: CurrentUser, session_id: str):
    session = load_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    return session


@router.post("/{session_id}/message")
def post_message(_user: CurrentUser, session_id: str, body: SendMessageBody):
    try:
        return send_message(session_id, body.message)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{session_id}/confirm")
def confirm(_user: CurrentUser, session_id: str, body: ConfirmBody):
    try:
        return confirm_action(
            session_id, body.action_id, tool_args_override=body.tool_args
        )
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/{session_id}/cancel")
def cancel(_user: CurrentUser, session_id: str):
    try:
        return cancel_pending(session_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
