import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.security import (
    create_session_token,
    decode_session_token,
    hash_password,
    verify_password,
    InvalidSessionToken,
)
from app.main import app, check_production_settings
from app.models import EmailToken, SearchLog, Subscription, SubscriptionStatus, User
from app.services.email import MemoryEmailSender, get_email_sender
from app.services.quota import get_quota, month_start

PW = "guvenli-sifre-123"
EMAIL = "Avukat@Ornek.com"


@pytest.fixture
def mailer():
    return MemoryEmailSender()


@pytest.fixture
def client(db, mailer):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_email_sender] = lambda: mailer
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _token_from(mailer: MemoryEmailSender) -> str:
    return re.search(r"jeton=([\w-]+)", mailer.outbox[-1].body).group(1)


def _register_and_verify(client, mailer, email=EMAIL, password=PW):
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 202
    assert client.post("/auth/verify-email", json={"token": _token_from(mailer)}).status_code == 200


# --- Güvenlik yardımcıları -------------------------------------------------------


def test_password_hashing():
    h = hash_password(PW)
    assert h.startswith("$argon2") and PW not in h
    assert verify_password(PW, h)
    assert not verify_password("yanlis-sifre-1", h)
    assert not verify_password(PW, None)
    assert not verify_password(PW, "bozuk-hash")


def test_session_token_roundtrip_and_tamper():
    tok = create_session_token(42)
    uid, iat = decode_session_token(tok)
    assert uid == 42 and iat <= datetime.now(timezone.utc)
    with pytest.raises(InvalidSessionToken):
        decode_session_token(tok[:-2] + ("aa" if tok[-2:] != "aa" else "bb"))
    other = Settings(secret_key="baska-bir-anahtar-" * 3)
    with pytest.raises(InvalidSessionToken):
        decode_session_token(create_session_token(42, other))
    expired = create_session_token(42, now=datetime.now(timezone.utc) - timedelta(days=30))
    with pytest.raises(InvalidSessionToken):
        decode_session_token(expired)


def test_production_settings_are_checked():
    check_production_settings(Settings(app_env="development"))
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        check_production_settings(Settings(app_env="production"))
    check_production_settings(Settings(app_env="production", secret_key="x" * 40,
                                       cookie_secure=True, email_backend="smtp"))


# --- Kayıt ve doğrulama ----------------------------------------------------------


def test_register_verify_login_me_logout(client, mailer, db):
    r = client.post("/auth/register", json={"email": EMAIL, "password": PW, "full_name": " Av. Ayşe "})
    assert r.status_code == 202
    user = db.scalars(select(User)).one()
    assert user.email == "avukat@ornek.com" and user.full_name == "Av. Ayşe"
    assert user.password_hash != PW and not user.email_verified
    assert len(mailer.outbox) == 1 and mailer.outbox[0].to == "avukat@ornek.com"
    raw = _token_from(mailer)
    # Jetonun kendisi değil, yalnızca özeti saklanır
    assert db.scalars(select(EmailToken)).one().token_hash != raw

    # Doğrulamadan giriş yapılamaz
    assert client.post("/auth/login", json={"email": EMAIL, "password": PW}).status_code == 403

    assert client.post("/auth/verify-email", json={"token": raw}).status_code == 200
    # Jeton tek kullanımlık
    assert client.post("/auth/verify-email", json={"token": raw}).status_code == 400

    r = client.post("/auth/login", json={"email": "avukat@ornek.com", "password": PW})
    assert r.status_code == 200 and r.json()["email_verified"] is True
    cookie = r.headers["set-cookie"]
    assert "ictihat_oturum=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()

    me = client.get("/auth/me").json()
    assert me["kullanici"]["email"] == "avukat@ornek.com"
    assert me["kota"] == {**me["kota"], "sinirsiz": False, "kullanilan": 0, "hak": 3, "kalan": 3}
    assert "password_hash" not in me["kullanici"]

    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401


def test_register_does_not_reveal_existing_accounts(client, mailer):
    _register_and_verify(client, mailer)
    r = client.post("/auth/register", json={"email": "avukat@ornek.com", "password": "baska-sifre-99"})
    assert r.status_code == 202
    assert mailer.outbox[-1].subject.startswith("Bu e-posta adresiyle zaten")
    # Şifre değişmedi
    assert client.post("/auth/login", json={"email": EMAIL, "password": PW}).status_code == 200


def test_resend_verification_invalidates_old_token(client, mailer):
    client.post("/auth/register", json={"email": EMAIL, "password": PW})
    old = _token_from(mailer)
    r = client.post("/auth/resend-verification", json={"email": EMAIL})
    assert r.status_code == 202
    new = _token_from(mailer)
    assert old != new
    assert client.post("/auth/verify-email", json={"token": old}).status_code == 400
    assert client.post("/auth/verify-email", json={"token": new}).status_code == 200
    # Bilinmeyen adres için de aynı yanıt, e-posta gönderilmez
    n = len(mailer.outbox)
    r2 = client.post("/auth/resend-verification", json={"email": "yok@ornek.com"})
    assert r2.status_code == 202 and r2.json() == r.json() and len(mailer.outbox) == n


def test_expired_verification_token(client, mailer, db):
    client.post("/auth/register", json={"email": EMAIL, "password": PW})
    tok = db.scalars(select(EmailToken)).one()
    tok.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert client.post("/auth/verify-email", json={"token": _token_from(mailer)}).status_code == 400


@pytest.mark.parametrize("password", ["kisa1", "sadeceharfler", "1234567890123", " bosluklu-sifre1"])
def test_weak_passwords_rejected(client, password):
    r = client.post("/auth/register", json={"email": EMAIL, "password": password})
    assert r.status_code == 422


def test_invalid_email_rejected(client):
    assert client.post("/auth/register", json={"email": "gecersiz", "password": PW}).status_code == 422


def test_login_errors_are_generic(client, mailer):
    _register_and_verify(client, mailer)
    a = client.post("/auth/login", json={"email": EMAIL, "password": "yanlis-sifre-1"})
    b = client.post("/auth/login", json={"email": "yok@ornek.com", "password": PW})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_inactive_user_cannot_login_or_use_session(client, mailer, db):
    _register_and_verify(client, mailer)
    assert client.post("/auth/login", json={"email": EMAIL, "password": PW}).status_code == 200
    user = db.scalars(select(User)).one()
    user.is_active = False
    db.commit()
    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/login", json={"email": EMAIL, "password": PW}).status_code == 401


def test_bad_session_cookie(client):
    client.cookies.set("ictihat_oturum", "bozuk.jeton.degeri")
    assert client.get("/auth/me").status_code == 401
    client.cookies.set("ictihat_oturum", create_session_token(999999))
    assert client.get("/auth/me").status_code == 401


# --- Şifre sıfırlama ---------------------------------------------------------------


def test_password_reset_flow(client, mailer, db):
    _register_and_verify(client, mailer)
    user = db.scalars(select(User)).one()
    # Sıfırlamadan önce düzenlenmiş eski bir oturum
    old_session = create_session_token(
        user.id, now=datetime.now(timezone.utc) - timedelta(minutes=5)
    )

    n = len(mailer.outbox)
    r = client.post("/auth/forgot-password", json={"email": "yok@ornek.com"})
    assert r.status_code == 202 and len(mailer.outbox) == n

    r2 = client.post("/auth/forgot-password", json={"email": EMAIL})
    assert r2.status_code == 202 and r2.json() == r.json()
    raw = _token_from(mailer)
    assert "/sifre-sifirla?jeton=" in mailer.outbox[-1].body

    # Uydurma jeton reddedilir
    bad = client.post("/auth/reset-password", json={"token": "x" * 20, "new_password": "yeni-sifre-456"})
    assert bad.status_code == 400

    new_pw = "yeni-sifre-456"
    assert client.post("/auth/reset-password", json={"token": raw, "new_password": new_pw}).status_code == 200
    assert client.post("/auth/reset-password", json={"token": raw, "new_password": new_pw}).status_code == 400

    assert client.post("/auth/login", json={"email": EMAIL, "password": PW}).status_code == 401
    assert client.post("/auth/login", json={"email": EMAIL, "password": new_pw}).status_code == 200
    assert client.get("/auth/me").status_code == 200

    # Eski oturum artık geçersiz
    client.cookies.set("ictihat_oturum", old_session)
    assert client.get("/auth/me").status_code == 401


def test_verify_token_cannot_reset_password(client, mailer):
    client.post("/auth/register", json={"email": EMAIL, "password": PW})
    raw = _token_from(mailer)
    r = client.post("/auth/reset-password", json={"token": raw, "new_password": "yeni-sifre-456"})
    assert r.status_code == 400


# --- Kota ---------------------------------------------------------------------------


def _user(db, email="kota@ornek.com"):
    u = User(email=email, password_hash=hash_password(PW), email_verified=True)
    db.add(u)
    db.flush()
    return u


def test_month_start_uses_istanbul_time():
    # 31 Ekim 22:30 UTC = 1 Kasım 01:30 İstanbul -> dönem 1 Kasım (31 Ekim 21:00 UTC)
    now = datetime(2026, 10, 31, 22, 30, tzinfo=timezone.utc)
    assert month_start(now, "Europe/Istanbul") == datetime(2026, 10, 31, 21, 0, tzinfo=timezone.utc)


def test_free_quota_counts_this_month_only(db):
    u = _user(db)
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    db.add(SearchLog(user_id=u.id, created_at=datetime(2026, 10, 15, tzinfo=timezone.utc),
                     query_length=10, result_count=1, result_decision_ids=[]))
    for _ in range(2):
        db.add(SearchLog(user_id=u.id, created_at=datetime(2026, 11, 5, tzinfo=timezone.utc),
                         query_length=10, result_count=1, result_decision_ids=[]))
    db.flush()
    q = get_quota(db, u, now=now)
    assert (q.used, q.limit, q.remaining, q.allowed, q.unlimited) == (2, 3, 1, True, False)

    db.add(SearchLog(user_id=u.id, created_at=datetime(2026, 11, 6, tzinfo=timezone.utc),
                     query_length=10, result_count=1, result_decision_ids=[]))
    db.flush()
    q = get_quota(db, u, now=now)
    assert (q.remaining, q.allowed) == (0, False)


def test_active_subscription_is_unlimited(db):
    u = _user(db)
    now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    db.add(Subscription(user_id=u.id, plan="aylik", status=SubscriptionStatus.ACTIVE,
                        current_period_end=now - timedelta(days=1)))
    db.flush()
    assert get_quota(db, u, now=now).unlimited is False  # süresi geçmiş
    db.add(Subscription(user_id=u.id, plan="aylik", status=SubscriptionStatus.ACTIVE,
                        current_period_end=now + timedelta(days=10)))
    db.flush()
    q = get_quota(db, u, now=now)
    assert q.unlimited and q.allowed and q.remaining is None


def test_settings_default_free_searches():
    assert get_settings().free_searches_per_month == 3
