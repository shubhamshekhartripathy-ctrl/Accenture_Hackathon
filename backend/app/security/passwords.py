"""PBKDF2-SHA256 password hashing (210k iterations) — standard library only."""
from __future__ import annotations

import hashlib
import hmac
import secrets


def hash_password(password: str, iterations: int = 210_000) -> tuple[str, str, int]:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations)
    return digest.hex(), salt, iterations


def verify_password(password: str, password_hash: str, salt: str, iterations: int) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations)
    return hmac.compare_digest(digest.hex(), password_hash)
