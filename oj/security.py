from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

import bcrypt

from oj.models import utcnow


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), encoded.encode())
    except ValueError:
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def session_expiry(hours: int):
    return utcnow() + timedelta(hours=hours)
