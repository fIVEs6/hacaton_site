"""Пароли (argon2), JWT, одноразовые токены, CSRF."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from app.core.config import settings

_ph = PasswordHasher()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def new_token() -> tuple[str, str]:
    """Возвращает (токен для письма, его SHA-256 для хранения в БД)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def check_password_strength(password: str) -> str | None:
    """Возвращает текст ошибки или None, если пароль подходит."""
    if len(password) < 8:
        return "Пароль должен содержать не менее 8 символов"
    if password.isdigit() or password.isalpha():
        return "Пароль должен содержать и буквы, и цифры"
    return None
