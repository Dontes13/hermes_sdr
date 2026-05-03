from typing import Annotated

from fastapi import Depends, Header, HTTPException

from agent.src.api.auth import decode_jwt
from agent.src.exceptions import AuthError


def current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Parse 'Authorization: Bearer <jwt>', decode, return subject.

    Raises HTTPException 401 on any failure.
    """
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Invalid Authorization header format")

    try:
        payload = decode_jwt(parts[1])
    except AuthError as e:
        raise HTTPException(401, str(e)) from e

    return payload.get("sub", "unknown")


CurrentUser = Annotated[str, Depends(current_user)]
