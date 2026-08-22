"""Auth dependencies: current user resolution, RBAC, login lockout.

Everything is server-side. The frontend is never the security boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import AppError
from ..models.org import User
from .jwt_auth import decode_token

_bearer = HTTPBearer(auto_error=False)

# Simple in-process login rate limiter (per email+ip). Redis-backed upgrade lands with S6.
_login_attempts: dict[str, list[float]] = {}


def check_login_rate_limit(key: str) -> None:
    from ..config import settings as _settings
    now = time_now()
    bucket = [t for t in _login_attempts.get(key, []) if now - t < 60]
    if len(bucket) >= _settings.login_rate_per_minute:
        raise AppError("RATE_LIMITED", "Too many login attempts — wait a minute and retry", 429)
    bucket.append(now)
    _login_attempts[key] = bucket


def time_now() -> float:
    return datetime.now(timezone.utc).timestamp()


def is_locked(user: User) -> bool:
    if not user.locked_until:
        return False
    locked_until = user.locked_until
    if locked_until.tzinfo is None:  # SQLite returns naive datetimes; stored values are UTC
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > datetime.now(timezone.utc)


def register_failure(user: User, db: Session) -> None:
    from ..config import settings

    user.failed_attempts = (user.failed_attempts or 0) + 1
    if user.failed_attempts >= settings.login_max_failures:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.login_lockout_minutes)
        user.failed_attempts = 0
    db.add(user)
    db.commit()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise AppError("UNAUTHORIZED", "Missing bearer token", 401)
    payload = decode_token(credentials.credentials)
    if payload.get("typ") != "access":
        raise AppError("UNAUTHORIZED", "Wrong token type", 401)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user is None or not user.is_active:
        raise AppError("UNAUTHORIZED", "User not found or inactive", 401)
    # Tenant cross-check: token org must match the user's org.
    if user.organization_id != payload.get("org"):
        raise AppError("UNAUTHORIZED", "Token/tenant mismatch", 401)
    if is_locked(user):
        raise AppError("UNAUTHORIZED", "Account locked — try again later", 401)
    request.state.actor = user
    return user


def require_roles(*roles: str):
    """Route guard factory — 403 with an audited denial when the role is not permitted."""

    def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles and user.role != "ADMIN":
            raise AppError("FORBIDDEN", f"Role {user.role} is not permitted for this operation", 403)
        return user

    return _guard
