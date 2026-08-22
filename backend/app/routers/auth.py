"""Auth router — real JWT auth with PBKDF2 verification, lockout, audit."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..envelope import ok
from ..errors import AppError
from ..models.org import User
from ..security import verify_password
from ..security.deps import check_login_rate_limit, get_current_user, is_locked, register_failure
from ..security.jwt_auth import create_token, decode_token
from ..services.audit import record as audit

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: str
    password: str


class RefreshBody(BaseModel):
    refresh_token: str


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "job_title": user.job_title,
        "region_scope": user.region_scope,
        "organization_id": user.organization_id,
        "organization": user.organization.name if user.organization else None,
    }


@router.post("/login")
def login(body: LoginBody, request: Request, db: Session = Depends(get_db)):
    check_login_rate_limit(f"{body.email.lower()}|{request.client.host if request.client else 'unknown'}")
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    request_id = getattr(request.state, "request_id", None)
    if user is None or user.organization_id is None:
        audit(db, "", "auth.login", "user", None, outcome="failure", details={"email": body.email, "reason": "unknown_user"}, request_id=request_id)
        raise AppError("UNAUTHORIZED", "Invalid email or password", 401)
    if is_locked(user):
        audit(db, user.organization_id, "auth.login", "user", user.id, outcome="denied", details={"reason": "locked"}, request_id=request_id)
        raise AppError("UNAUTHORIZED", "Account temporarily locked after repeated failures — try again later", 401)
    if not verify_password(body.password, user.password_hash, user.password_salt, user.pbkdf2_iterations):
        register_failure(user, db)
        audit(db, user.organization_id, "auth.login", "user", user.id, outcome="failure", details={"reason": "bad_password", "failed_attempts": user.failed_attempts}, request_id=request_id)
        raise AppError("UNAUTHORIZED", "Invalid email or password", 401)
    user.failed_attempts = 0
    user.locked_until = None
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    audit(db, user.organization_id, "auth.login", "user", user.id, actor_user_id=user.id, actor_role=user.role, request_id=request_id)
    return ok(
        request,
        {
            "access_token": create_token(user.id, user.organization_id, user.role, "access"),
            "refresh_token": create_token(user.id, user.organization_id, user.role, "refresh"),
            "user": _user_payload(user),
        },
    )


@router.post("/refresh")
def refresh(body: RefreshBody, request: Request, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload.get("typ") != "refresh":
        raise AppError("UNAUTHORIZED", "Refresh token required", 401)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user is None or not user.is_active:
        raise AppError("UNAUTHORIZED", "User not found or inactive", 401)
    return ok(
        request,
        {
            "access_token": create_token(user.id, user.organization_id, user.role, "access"),
            "refresh_token": create_token(user.id, user.organization_id, user.role, "refresh"),
            "user": _user_payload(user),
        },
    )


@router.get("/me")
def me(request: Request, user: User = Depends(get_current_user)):
    return ok(request, _user_payload(user))
