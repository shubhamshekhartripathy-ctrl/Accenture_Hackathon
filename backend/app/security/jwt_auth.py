"""Minimal, dependency-free HS256 JWT (access + refresh) per RFC 7519 semantics.

No external jose library needed; signing key comes from Settings. Claims:
sub (user id), org, role, typ (access|refresh), iat, exp, jti.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from ..config import settings
from ..errors import AppError


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign(payload: bytes) -> str:
    key = settings.effective_secret_key().encode("utf-8")
    return _b64url(hmac.new(key, payload, hashlib.sha256).digest())


def create_token(user_id: str, organization_id: str, role: str, token_type: str = "access") -> str:
    now = int(time.time())
    if token_type == "access":
        exp = now + settings.access_token_minutes * 60
    else:
        exp = now + settings.refresh_token_days * 86400
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id, "org": organization_id, "role": role, "typ": token_type, "iat": now, "exp": exp, "jti": uuid.uuid4().hex}
    signing_input = _b64url(json.dumps(header, separators=(",", ":")).encode()) + "." + _b64url(
        json.dumps(payload, separators=(",", ":")).encode()
    )
    return signing_input + "." + _sign(signing_input.encode())


def decode_token(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError:
        raise AppError("UNAUTHORIZED", "Malformed token", 401)
    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected = _sign(signing_input)
    if not hmac.compare_digest(expected, sig_b64):
        raise AppError("UNAUTHORIZED", "Invalid token signature", 401)
    payload = json.loads(_b64url_decode(payload_b64))
    if payload.get("exp", 0) < time.time():
        raise AppError("UNAUTHORIZED", "Token expired", 401)
    return payload
