from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models import User
from app.models.enums import Role
from app.schemas.common import In
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(In):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)
    role: Role


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: Role


class LoginOut(BaseModel):
    access_token: str
    token_type: str
    expires_at: str
    user: UserOut


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, body.username, body.password, body.role)
    return auth_service.issue_token(user)


@router.get("/me", response_model=UserOut)
def me(user: User = CurrentUser):
    return auth_service.user_out(user)


@router.post("/logout", status_code=204)
def logout(_: User = CurrentUser):
    return Response(status_code=204)
