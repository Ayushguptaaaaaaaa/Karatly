from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models import User
from app.models.enums import Role


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _token_from_request(request)
    if not token:
        raise AppError("UNAUTHORIZED", "Please log in to continue.", 401)
    try:
        claims = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise AppError("TOKEN_EXPIRED", "Your session has expired. Please log in again.", 401)
    except jwt.PyJWTError:
        raise AppError("UNAUTHORIZED", "Invalid session. Please log in again.", 401)
    user = db.get(User, int(claims.get("sub", 0)))
    if not user or not user.is_active:
        raise AppError("UNAUTHORIZED", "Account not found or disabled.", 401)
    return user


def require_roles(*roles: Role) -> Callable[..., User]:
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError("FORBIDDEN", "Only the shop owner can do this.", 403)
        return user

    return _dep


CurrentUser = Depends(get_current_user)
OwnerOnly = Depends(require_roles(Role.OWNER))
