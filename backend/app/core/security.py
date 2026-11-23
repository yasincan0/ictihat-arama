"""Şifre hash'leme, oturum jetonu (JWT) ve tek kullanımlık e-posta jetonları."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings, get_settings

_hasher = PasswordHasher()

# Kullanıcı bulunamadığında da aynı sürede yanıt vermek için kullanılan sahte hash
_DUMMY_HASH = _hasher.hash("zamanlama-icin-sahte-sifre")

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Şifreyi doğrular. Hash yoksa da sahte bir doğrulama yapılır (zamanlama saldırısına karşı)."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_session_token(user_id: int, settings: Settings | None = None,
                         now: datetime | None = None) -> str:
    settings = settings or get_settings()
    now = now or _now()
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.session_ttl_minutes)).timestamp()),
        "typ": "oturum",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


class InvalidSessionToken(Exception):
    pass


def decode_session_token(token: str, settings: Settings | None = None) -> tuple[int, datetime]:
    """(kullanıcı id, düzenlenme zamanı) döndürür; geçersizse InvalidSessionToken."""
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "iat", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidSessionToken(str(exc)) from exc
    if payload.get("typ") != "oturum":
        raise InvalidSessionToken("jeton türü hatalı")
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise InvalidSessionToken("sub hatalı") from exc
    return user_id, datetime.fromtimestamp(payload["iat"], tz=timezone.utc)


def new_email_token() -> tuple[str, str]:
    """(kullanıcıya gönderilecek ham jeton, veritabanında saklanacak SHA-256 özeti)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_email_token(raw)


def hash_email_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
