from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.models.enums import Role
from app.services import audit_service

ROLE_WORD = {Role.OWNER: "Owner", Role.ADMIN: "Admin"}


def seed_users(db: Session) -> None:
    s = get_settings()
    wanted = [
        (s.SEED_OWNER_USERNAME, s.SEED_OWNER_PASSWORD, Role.OWNER, "Owner"),
        (s.SEED_ADMIN_USERNAME, s.SEED_ADMIN_PASSWORD, Role.ADMIN, "Admin"),
    ]
    for username, password, role, display in wanted:
        username = username.strip().lower()
        if not db.query(User).filter(User.username == username).first():
            db.add(User(username=username, password_hash=hash_password(password), role=role, display_name=display))
    db.commit()


def authenticate(db: Session, username: str, password: str, role: Role) -> User:
    user = db.query(User).filter(User.username == username.strip().lower()).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Incorrect username or password.", 401)
    if user.role != role:
        raise AppError(
            "ROLE_MISMATCH",
            f"This account is not an {ROLE_WORD[role]} account. Go back and choose the right login.",
            403,
            {"account_role": user.role.value},
        )
    user.last_login_at = now_utc()
    audit_service.log(db, user, "LOGIN", "user", user.id)
    db.commit()
    return user


def issue_token(user: User) -> dict:
    token, exp = create_access_token(user.id, user.role.value)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": exp.isoformat(),
        "user": user_out(user),
    }


def user_out(user: User) -> dict:
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role.value}
