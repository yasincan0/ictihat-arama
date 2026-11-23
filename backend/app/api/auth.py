"""Üyelik uç noktaları: kayıt, e-posta doğrulama, giriş/çıkış, şifre sıfırlama.

Güvenlik notları:
- Kayıt, doğrulama e-postasını yeniden gönderme ve şifremi unuttum uç noktaları, e-posta
  adresinin sistemde olup olmadığını belli etmez (her zaman aynı yanıt).
- Oturum jetonu HttpOnly + SameSite=Lax çerezde taşınır; JavaScript erişemez.
- E-posta jetonları tek kullanımlıktır, süreli tutulur ve yalnızca özetleri saklanır.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.ratelimit import client_ip, limit
from app.core.security import (
    create_session_token,
    hash_email_token,
    hash_password,
    new_email_token,
    password_needs_rehash,
    verify_password,
)
from app.models import EmailToken, EmailTokenPurpose, User
from app.schemas.auth import (
    DeleteAccountRequest,
    EmailRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    QuotaResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenRequest,
    UserResponse,
)
from app.services.email import EmailSender, get_email_sender
from app.services.email import templates
from app.services.quota import get_quota

router = APIRouter(prefix="/auth", tags=["üyelik"])

MSG_REGISTERED = (
    "Kayıt isteğiniz alındı. E-posta adresinize gönderilen bağlantıyla hesabınızı doğrulayın."
)
MSG_VERIFICATION_SENT = (
    "Bu adrese ait doğrulanmamış bir hesap varsa doğrulama bağlantısı gönderildi."
)
MSG_RESET_SENT = "Bu adrese ait bir hesap varsa şifre sıfırlama bağlantısı gönderildi."
MSG_INVALID_TOKEN = "Bağlantı geçersiz veya süresi dolmuş"
MSG_BAD_LOGIN = "E-posta adresi veya şifre hatalı"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _find_user(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == normalize_email(email))).first()


def _issue_token(db: Session, user: User, purpose: EmailTokenPurpose, ttl: timedelta) -> str:
    """Aynı amaçlı önceki kullanılmamış jetonları geçersiz kılar, yenisini üretir."""
    now = _now()
    db.execute(
        update(EmailToken)
        .where(EmailToken.user_id == user.id, EmailToken.purpose == purpose,
               EmailToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw, digest = new_email_token()
    db.add(EmailToken(user_id=user.id, purpose=purpose, token_hash=digest, expires_at=now + ttl))
    return raw


def _consume_token(db: Session, raw: str, purpose: EmailTokenPurpose) -> EmailToken | None:
    token = db.scalars(
        select(EmailToken).where(EmailToken.token_hash == hash_email_token(raw)).with_for_update()
    ).first()
    now = _now()
    if token is None or token.purpose != purpose or token.used_at is not None \
            or token.expires_at <= now:
        return None
    token.used_at = now
    return token


def _send_verification(db: Session, user: User, mailer: EmailSender, settings: Settings) -> None:
    raw = _issue_token(db, user, EmailTokenPurpose.VERIFY_EMAIL,
                       timedelta(hours=settings.email_verify_ttl_hours))
    db.commit()
    mailer.send(templates.verify_email(user.email, raw, settings))


@router.post("/register", status_code=status.HTTP_202_ACCEPTED, response_model=MessageResponse)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db),
             mailer: EmailSender = Depends(get_email_sender)) -> MessageResponse:
    limit("register_ip", client_ip(request))
    limit("email_send_addr", normalize_email(body.email))
    settings = get_settings()
    existing = _find_user(db, body.email)
    if existing is not None:
        if existing.email_verified:
            mailer.send(templates.account_exists(existing.email, settings))
        else:
            _send_verification(db, existing, mailer, settings)
        return MessageResponse(mesaj=MSG_REGISTERED)

    user = User(
        email=normalize_email(body.email),
        password_hash=hash_password(body.password),
        full_name=(body.full_name or "").strip() or None,
        email_verified=False,
    )
    db.add(user)
    db.flush()
    _send_verification(db, user, mailer, settings)
    return MessageResponse(mesaj=MSG_REGISTERED)


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(body: TokenRequest, request: Request,
                 db: Session = Depends(get_db)) -> MessageResponse:
    limit("token_ip", client_ip(request))
    token = _consume_token(db, body.token, EmailTokenPurpose.VERIFY_EMAIL)
    if token is None:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, MSG_INVALID_TOKEN)
    token.user.email_verified = True
    db.commit()
    return MessageResponse(mesaj="E-posta adresiniz doğrulandı. Giriş yapabilirsiniz.")


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED,
             response_model=MessageResponse)
def resend_verification(body: EmailRequest, request: Request, db: Session = Depends(get_db),
                        mailer: EmailSender = Depends(get_email_sender)) -> MessageResponse:
    limit("email_send_ip", client_ip(request))
    limit("email_send_addr", normalize_email(body.email))
    user = _find_user(db, body.email)
    if user is not None and user.is_active and not user.email_verified:
        _send_verification(db, user, mailer, get_settings())
    return MessageResponse(mesaj=MSG_VERIFICATION_SENT)


def _set_session_cookie(response: Response, user: User, settings: Settings) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_session_token(user.id, settings),
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=UserResponse)
def login(body: LoginRequest, request: Request, response: Response,
          db: Session = Depends(get_db)) -> User:
    limit("login_ip", client_ip(request))
    limit("login_email", normalize_email(body.email))
    settings = get_settings()
    user = _find_user(db, body.email)
    if not verify_password(body.password, user.password_hash if user else None) \
            or user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MSG_BAD_LOGIN)
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Giriş yapmadan önce e-posta adresinizi doğrulayın")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
        db.commit()
    _set_session_cookie(response, user, settings)
    return user


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response) -> MessageResponse:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/", httponly=True,
                           secure=settings.cookie_secure, samesite="lax")
    return MessageResponse(mesaj="Oturum kapatıldı")


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    q = get_quota(db, user)
    return MeResponse(
        kullanici=UserResponse.model_validate(user),
        kota=QuotaResponse(sinirsiz=q.unlimited, kullanilan=q.used, hak=q.limit,
                           kalan=q.remaining, donem_baslangici=q.period_start),
    )


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED,
             response_model=MessageResponse)
def forgot_password(body: EmailRequest, request: Request, db: Session = Depends(get_db),
                    mailer: EmailSender = Depends(get_email_sender)) -> MessageResponse:
    limit("email_send_ip", client_ip(request))
    limit("email_send_addr", normalize_email(body.email))
    settings = get_settings()
    user = _find_user(db, body.email)
    if user is not None and user.is_active:
        raw = _issue_token(db, user, EmailTokenPurpose.RESET_PASSWORD,
                           timedelta(minutes=settings.password_reset_ttl_minutes))
        db.commit()
        mailer.send(templates.reset_password(user.email, raw, settings))
    return MessageResponse(mesaj=MSG_RESET_SENT)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, request: Request, response: Response,
                   db: Session = Depends(get_db)) -> MessageResponse:
    limit("token_ip", client_ip(request))
    token = _consume_token(db, body.token, EmailTokenPurpose.RESET_PASSWORD)
    if token is None or not token.user.is_active:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, MSG_INVALID_TOKEN)
    user = token.user
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = _now()
    # Bağlantı e-postaya geldiğine göre adres de doğrulanmış olur
    user.email_verified = True
    db.commit()
    # Bu tarayıcıdaki eski oturum da geçersizleşti; çerezi temizle
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    return MessageResponse(mesaj="Şifreniz değiştirildi. Yeni şifrenizle giriş yapabilirsiniz.")


@router.post("/delete-account", response_model=MessageResponse)
def delete_account(body: DeleteAccountRequest, request: Request, response: Response,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> MessageResponse:
    """Hesabı ve kişisel verileri kalıcı olarak siler (KVKK m.7, m.11).

    Abonelik, e-posta jetonları ve ödeme oturumları birlikte silinir; arama günlükleri
    (olay metni içermez) kullanıcıdan ayrılarak anonim istatistik olarak kalır.
    Etkin bir abonelik varken önce abonelik iptal edilmelidir (yenileme ücreti alınmasın).
    """
    limit("login_ip", client_ip(request))
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Şifre hatalı")
    from app.models import Subscription, SubscriptionStatus

    renewing = db.scalars(select(Subscription).where(
        Subscription.user_id == user.id,
        Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]),
    )).first()
    if renewing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Hesabınızı silmeden önce aboneliğinizi iptal edin")
    db.delete(user)
    db.commit()
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    return MessageResponse(mesaj="Hesabınız ve kişisel verileriniz silindi.")
