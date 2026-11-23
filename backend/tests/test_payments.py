import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import get_db
from app.core.security import create_session_token, hash_password
from app.main import app
from app.models import PaymentCheckout, Subscription, SubscriptionStatus, User
from app.schemas.payments import is_valid_tckn, normalize_tr_gsm
from app.services.payments import BillingInfo, PaymentError, get_payment_provider
from app.services.payments.fake import FakeProvider
from app.services.payments.iyzico import IyzicoProvider, auth_headers, webhook_signature
from app.services.quota import get_quota

BILLING = {"ad": "Ayşe", "soyad": "Yılmaz", "tckn": "10000000146", "telefon": "0532 123 45 67",
           "adres": "Örnek Mah. Test Sok. No:1", "sehir": "Ankara"}


@pytest.fixture(autouse=True)
def _payments(payments_on):
    yield


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def client(db, provider):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_payment_provider] = lambda: provider
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _login(client, db, verified=True, email="abone@ornek.com"):
    u = User(email=email, password_hash=hash_password("guvenli-sifre-1"), email_verified=verified)
    db.add(u)
    db.flush()
    client.cookies.set("ictihat_oturum", create_session_token(u.id))
    return u


def _subscribe(client, provider):
    r = client.post("/payments/checkout", json=BILLING)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return client.post("/payments/callback", content=f"token={token}",
                       headers={"Content-Type": "application/x-www-form-urlencoded"},
                       follow_redirects=False)


# --- Doğrulama yardımcıları ----------------------------------------------------------


def test_tckn_and_gsm():
    assert is_valid_tckn("10000000146") and is_valid_tckn("11111111110")
    assert not is_valid_tckn("12345678901") and not is_valid_tckn("01234567890")
    assert normalize_tr_gsm("0532 123 45 67") == "+905321234567"
    assert normalize_tr_gsm("+90 (532) 123-45-67") == "+905321234567"
    assert normalize_tr_gsm("5321234567") == "+905321234567"
    with pytest.raises(ValueError):
        normalize_tr_gsm("0212 123 45 67")


# --- Uçtan uca (sahte sağlayıcı) -----------------------------------------------------


def test_checkout_requires_login_and_verified_email(client, db):
    assert client.post("/payments/checkout", json=BILLING).status_code == 401
    _login(client, db, verified=False)
    assert client.post("/payments/checkout", json=BILLING).status_code == 403


def test_invalid_billing_rejected(client, db):
    _login(client, db)
    for field, value in [("tckn", "12345678901"), ("telefon", "123"), ("ad", "  ")]:
        assert client.post("/payments/checkout", json={**BILLING, field: value}).status_code == 422


def test_full_subscription_flow(client, db, provider):
    user = _login(client, db)
    assert client.get("/payments/subscription").json()["var"] is False

    r = _subscribe(client, provider)
    assert r.status_code == 303 and r.headers["location"].endswith("/abonelik?durum=basarili")
    # Fatura bilgileri sağlayıcıya iletildi ama veritabanında saklanmadı
    assert provider.last_billing.identity_number == "10000000146"
    assert provider.last_billing.gsm_number == "+905321234567"
    assert provider.last_billing.email == "abone@ornek.com"
    pc = db.scalars(select(PaymentCheckout)).one()
    assert pc.result == "basarili" and "10000000146" not in json.dumps(pc.__dict__, default=str)

    sub = client.get("/payments/subscription").json()
    assert sub["var"] is True and sub["durum"] == "active" and sub["iptal_edilebilir"]
    assert get_quota(db, user).unlimited

    # Aynı jetonla ikinci dönüş yeni abonelik oluşturmaz
    again = client.post("/payments/callback", content=f"token={pc.token}",
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        follow_redirects=False)
    assert again.headers["location"].endswith("durum=basarili")
    assert len(db.scalars(select(Subscription)).all()) == 1

    # Etkin abonelik varken yeni ödeme başlatılamaz
    assert client.post("/payments/checkout", json=BILLING).status_code == 409

    # İptal: yenileme durur, ödenmiş dönem sonuna kadar sınırsız devam eder
    r = client.post("/payments/cancel")
    assert r.status_code == 200 and "dönem sonuna" in r.json()["mesaj"]
    assert provider.canceled
    sub = client.get("/payments/subscription").json()
    assert sub["durum"] == "canceled" and sub["var"] is True and not sub["iptal_edilebilir"]
    assert client.post("/payments/cancel").status_code == 404


def test_callback_with_unknown_token_redirects_to_error(client):
    r = client.post("/payments/callback", content="token=bilinmeyen",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("durum=hata")


def test_webhook_updates_from_provider_not_payload(client, db, provider):
    _login(client, db)
    _subscribe(client, provider)
    sub = db.scalars(select(Subscription)).one()
    ref = sub.provider_subscription_id
    # Sağlayıcı tarafında yenileme oldu: dönem sonu ileri alındı
    info = provider.subscriptions[ref]
    new_end = info.current_period_end + timedelta(days=30)
    provider.subscriptions[ref] = type(info)(ref, info.customer_reference_code,
                                             SubscriptionStatus.ACTIVE, info.plan_reference_code,
                                             new_end)
    body = {"iyziEventType": "subscription.order.success", "subscriptionReferenceCode": ref,
            "orderReferenceCode": "o1", "customerReferenceCode": "c1",
            # gövdedeki alanlara güvenilmez
            "subscriptionStatus": "EXPIRED"}
    assert client.post("/payments/webhook/iyzico", json=body).status_code == 401
    r = client.post("/payments/webhook/iyzico", json=body, headers={"x-fake-signature": "gecerli"})
    assert r.status_code == 200 and r.json() == {"durum": "islendi"}
    db.refresh(sub)
    assert sub.status == SubscriptionStatus.ACTIVE and sub.current_period_end == new_end

    unknown = {**body, "subscriptionReferenceCode": "yok"}
    r = client.post("/payments/webhook/iyzico", json=unknown, headers={"x-fake-signature": "gecerli"})
    assert r.json() == {"durum": "yok_sayildi"}
    assert client.post("/payments/webhook/iyzico", content="bozuk",
                       headers={"x-fake-signature": "gecerli"}).status_code == 400


def test_canceled_subscription_after_period_end_is_not_unlimited(db):
    u = User(email="x@ornek.com", password_hash="x", email_verified=True)
    db.add(u)
    db.flush()
    now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    db.add(Subscription(user_id=u.id, plan="aylik", status=SubscriptionStatus.CANCELED,
                        current_period_end=now - timedelta(days=1)))
    db.flush()
    assert not get_quota(db, u, now=now).unlimited
    db.add(Subscription(user_id=u.id, plan="aylik", status=SubscriptionStatus.CANCELED,
                        current_period_end=now + timedelta(days=5)))
    db.flush()
    assert get_quota(db, u, now=now).unlimited


def test_plan_endpoint(client):
    r = client.get("/payments/plan").json()
    assert r["ucretsiz_arama_hakki"] == 3 and "saglayici" in r


# --- iyzico istemcisi ---------------------------------------------------------------


def test_iyzico_auth_header_format():
    h = auth_headers("api-key", "secret", "/v2/x", '{"a":1}', random_key="123456789")
    decoded = base64.b64decode(h["Authorization"].removeprefix("IYZWSv2 ")).decode()
    sig = hmac.new(b"secret", b'123456789/v2/x{"a":1}', hashlib.sha256).hexdigest()
    assert decoded == f"apiKey:api-key&randomKey:123456789&signature:{sig}"
    assert h["x-iyzi-rnd"] == "123456789"


def _iyzico(handler, **kw):
    client = httpx.Client(base_url="https://sandbox-api.iyzipay.com",
                          transport=httpx.MockTransport(handler))
    return IyzicoProvider("api-key", "secret", "https://sandbox-api.iyzipay.com",
                          merchant_id="m1", client=client, **kw)


def _billing():
    return BillingInfo("Ayşe", "Yılmaz", "a@ornek.com", "+905321234567", "10000000146",
                       "Adres", "Ankara")


def test_iyzico_checkout_and_subscription_parsing():
    seen = []
    end_ms = int(datetime(2026, 12, 20, tzinfo=timezone.utc).timestamp() * 1000)

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path == "/v2/subscription/checkoutform/initialize":
            return httpx.Response(200, json={"status": "success", "token": "tok",
                                             "checkoutFormContent": "<script></script>",
                                             "tokenExpireTime": 1800})
        if req.url.path == "/v2/subscription/checkoutform/tok":
            return httpx.Response(200, json={"status": "success", "data": {"referenceCode": "sub1"}})
        if req.url.path == "/v2/subscription/subscriptions/sub1":
            return httpx.Response(200, json={"status": "success", "data": {"items": [{
                "referenceCode": "sub1", "customerReferenceCode": "cus1",
                "subscriptionStatus": "ACTIVE", "pricingPlanReferenceCode": "plan1",
                "orders": [
                    {"orderStatus": "SUCCESS", "endPeriod": end_ms - 30 * 86400000},
                    {"orderStatus": "SUCCESS", "endPeriod": end_ms},
                    {"orderStatus": "WAITING", "endPeriod": end_ms + 30 * 86400000},
                ]}]}})
        return httpx.Response(404, json={"status": "failure", "errorMessage": "bulunamadı"})

    p = _iyzico(handler)
    s = p.start_checkout(_billing(), "plan1", "https://api.ornek/cb", "odeme-1")
    assert (s.token, s.expires_in_seconds) == ("tok", 1800)
    sent = json.loads(seen[0].content)
    assert sent["customer"]["identityNumber"] == "10000000146"
    assert sent["customer"]["billingAddress"]["contactName"] == "Ayşe Yılmaz"
    assert sent["pricingPlanReferenceCode"] == "plan1" and sent["subscriptionInitialStatus"] == "ACTIVE"
    # İmza tam olarak gönderilen gövde üzerinden hesaplanmalı
    rnd = seen[0].headers["x-iyzi-rnd"]
    assert seen[0].headers["Authorization"] == auth_headers(
        "api-key", "secret", "/v2/subscription/checkoutform/initialize", seen[0].content.decode(),
        random_key=rnd)["Authorization"]

    info = p.retrieve_checkout("tok")
    assert info.reference_code == "sub1" and info.status == SubscriptionStatus.ACTIVE
    assert info.customer_reference_code == "cus1"
    assert info.current_period_end == datetime(2026, 12, 20, tzinfo=timezone.utc)

    with pytest.raises(PaymentError, match="bulunamadı"):
        p.get_subscription("yok")


def test_iyzico_network_error_is_friendly():
    def handler(req):
        raise httpx.ConnectError("x")

    with pytest.raises(PaymentError, match="ulaşılamadı"):
        _iyzico(handler).cancel("sub1")


def test_iyzico_webhook_signature():
    p = _iyzico(lambda r: httpx.Response(500))
    payload = {"iyziEventType": "subscription.order.success", "subscriptionReferenceCode": "s",
               "orderReferenceCode": "o", "customerReferenceCode": "c", "iyziEventTime": 1}
    sig = hmac.new(b"secret", b"m1secretsubscription.order.successsoc", hashlib.sha256).hexdigest()
    assert webhook_signature("m1", "secret", "subscription.order.success", "s", "o", "c") == sig
    ev = p.parse_webhook(payload, {"X-IYZ-SIGNATURE-V3": sig})
    assert ev.subscription_reference_code == "s"
    with pytest.raises(PaymentError, match="geçersiz"):
        p.parse_webhook(payload, {"X-IYZ-SIGNATURE-V3": "0" * 64})
    with pytest.raises(PaymentError, match="imzası yok"):
        p.parse_webhook(payload, {})
    lax = _iyzico(lambda r: httpx.Response(500), require_webhook_signature=False)
    assert lax.parse_webhook(payload, {}).event_type == "subscription.order.success"


def test_payments_disabled_returns_404(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("PAYMENTS_ENABLED", "false")
    get_settings.cache_clear()
    assert client.get("/payments/plan").status_code == 404
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    get_settings.cache_clear()
