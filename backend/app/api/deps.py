"""Ortak FastAPI bağımlılıkları: oturumdaki kullanıcı."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import InvalidSessionToken, decode_session_token
from app.models import User

NOT_AUTHENTICATED = "Oturum açmanız gerekiyor"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_AUTHENTICATED)
    try:
        user_id, issued_at = decode_session_token(token, settings)
    except InvalidSessionToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_AUTHENTICATED) from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_AUTHENTICATED)
    # Şifre değiştiyse eski oturumlar geçersiz (iat saniye hassasiyetinde)
    if user.password_changed_at and issued_at < user.password_changed_at.replace(microsecond=0):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_AUTHENTICATED)
    return user


def get_verified_user(user: User = Depends(get_current_user)) -> User:
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "E-posta adresinizi doğrulamanız gerekiyor")
    return user
