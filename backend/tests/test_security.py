import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import get_db
from app.core.logging import RedactingFilter, install_redaction, redact
from app.core.ratelimit import MemoryRateLimiter
from app.main import app, check_production_settings
from app.services.email import MemoryEmailSender, get_email_sender

ORIGIN = "http://localhost:3000"


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_email_sender] = lambda: MemoryEmailSender()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --- İstek sınırlama -----------------------------------------------------------------


def test_memory_rate_limiter_window():
    now = [0.0]
    rl = MemoryRateLimiter(clock=lambda: now[0])
    assert [rl.hit("k", 3, 60) for _ in range(3)] == [None, None, None]
    assert rl.hit("k", 3, 60) == pytest.approx(60)
    assert rl.hit("baska", 3, 60) is None
    now[0] = 61
    assert rl.hit("k", 3, 60) is None


def test_login_rate_limited_per_email(client):
    body = {"email": "hedef@ornek.com", "password": "yanlis-sifre-1"}
    codes = [client.post("/auth/login", json=body).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429
    r = client.post("/auth/login", json=body)
    assert int(r.headers["Retry-After"]) > 0 and "Çok fazla" in r.json()["detail"]
    # Başka hesap için IP sınırı henüz dolmadı
    assert client.post("/auth/login", json={**body, "email": "baska@ornek.com"}).status_code == 401


def test_password_reset_emails_limited_per_address(client):
    codes = [client.post("/auth/forgot-password", json={"email": "x@ornek.com"}).status_code
             for _ in range(4)]
    assert codes == [202, 202, 202, 429]


def test_x_forwarded_for_ignored_unless_trusted(client, monkeypatch):
    from app.core import ratelimit

    body = {"email": "y@ornek.com", "password": "yanlis-sifre-1"}
    # Saldırgan başlığı değiştirerek sınırı aşamaz (vekil güvenilir değil)
    for i in range(20):
        client.post("/auth/login", json={**body, "email": f"u{i}@ornek.com"},
                    headers={"X-Forwarded-For": f"10.0.0.{i}"})
    assert client.post("/auth/login", json=body, headers={"X-Forwarded-For": "10.9.9.9"}).status_code == 429

    monkeypatch.setattr(ratelimit, "get_settings", lambda: Settings(trusted_proxy_count=1))
    from starlette.requests import Request

    req = Request({"type": "http", "headers": [(b"x-forwarded-for", b"1.1.1.1, 2.2.2.2")],
                   "client": ("9.9.9.9", 1)})
    assert ratelimit.client_ip(req) == "2.2.2.2"


# --- Ara katmanlar --------------------------------------------------------------------


def test_security_headers(client):
    h = client.get("/health").headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "no-referrer"
    assert h["Cache-Control"] == "no-store"


def test_cross_origin_post_rejected(client):
    body = {"email": "z@ornek.com", "password": "yanlis-sifre-1"}
    r = client.post("/auth/login", json=body, headers={"Origin": "https://kotu.example"})
    assert r.status_code == 403
    assert client.post("/auth/logout", headers={"Origin": "https://kotu.example"}).status_code == 403
    assert client.post("/auth/login", json=body, headers={"Origin": ORIGIN}).status_code == 401
    # Origin'siz (tarayıcı dışı) istemci etkilenmez
    assert client.post("/auth/login", json=body).status_code == 401
    # Ödeme kuruluşunun çağırdığı uçlar muaf (kendi doğrulamaları var)
    r = client.post("/payments/callback", content="token=x", follow_redirects=False,
                    headers={"Origin": "https://sandbox-api.iyzipay.com",
                             "Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 303


def test_cors_preflight_allows_only_frontend(client):
    ok = client.options("/auth/login", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST",
                                                "Access-Control-Request-Headers": "content-type"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == ORIGIN
    assert ok.headers["access-control-allow-credentials"] == "true"
    bad = client.options("/auth/login", headers={"Origin": "https://kotu.example",
                                                 "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


def test_body_size_limit(client):
    big = "a" * (70 * 1024)
    r = client.post("/auth/login", content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413

    def chunks():  # Content-Length olmadan akış
        for _ in range(80):
            yield b"a" * 1024

    r = client.post("/auth/login", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_production_rejects_wildcard_or_http_cors():
    base = dict(app_env="production", secret_key="x" * 40, cookie_secure=True,
                email_backend="smtp", payment_provider="iyzico",
                iyzico_base_url="https://api.iyzipay.com")
    check_production_settings(Settings(**base, cors_origins="https://ictihat.example"))
    with pytest.raises(RuntimeError, match="'\\*'"):
        check_production_settings(Settings(**base, cors_origins="*"))
    with pytest.raises(RuntimeError, match="https"):
        check_production_settings(Settings(**base, cors_origins="http://ictihat.example"))


# --- Günlük maskeleme -----------------------------------------------------------------


def test_redact_patterns():
    s = redact("tckn 10000000146 tel +90 532 123 45 67 / 05321234567 kart 5528 7900 0000 0008 yil 2026")
    assert "10000000146" not in s and "532 123" not in s and "05321234567" not in s
    assert "5528" not in s and "2026" in s


def test_log_records_are_redacted(caplog):
    install_redaction()
    with caplog.at_level(logging.INFO, logger="app.deneme"):
        logging.getLogger("app.deneme").info("kimlik %s", "10000000146")
    assert "10000000146" not in caplog.text and "[TCKN?]" in caplog.text
    rec = logging.LogRecord("x", logging.INFO, "", 0, "biçim hatası %s %s", ("tek",), None)
    assert RedactingFilter().filter(rec)  # biçimlendirme hatası günlüğü düşürmez


def test_no_endpoint_logs_request_bodies():
    """Kaynak kodda istek gövdesini veya olay metnini günlüğe yazan çağrı olmamalı."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in root.rglob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"logger\.\w+\(.*\b(body|payload|request\.json|olay|query_text)\b", line):
                offenders.append(f"{path.name}:{i}")
    assert offenders == []
