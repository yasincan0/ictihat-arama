"""iyzico Abonelik API istemcisi (ham HTTP, SDK'sız).

Kaynak: docs.iyzico.com — HMACSHA256 (IYZWSv2) kimlik doğrulama, abonelik ödeme formu,
abonelik sorgulama/iptal ve X-IYZ-SIGNATURE-V3 webhook imzası.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.models import SubscriptionStatus
from app.services.payments.base import (
    BillingInfo,
    CheckoutSession,
    PaymentError,
    SubscriptionInfo,
    WebhookEvent,
)

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "ACTIVE": SubscriptionStatus.ACTIVE,
    "PENDING": SubscriptionStatus.PAST_DUE,
    "UNPAID": SubscriptionStatus.PAST_DUE,
    "CANCELED": SubscriptionStatus.CANCELED,
    "EXPIRED": SubscriptionStatus.EXPIRED,
    "UPGRADED": SubscriptionStatus.EXPIRED,
}


def auth_headers(api_key: str, secret_key: str, path: str, body: str,
                 random_key: str | None = None) -> dict[str, str]:
    """IYZWSv2: base64("apiKey:..&randomKey:..&signature:" + HMACSHA256(rnd + path + body))."""
    rnd = random_key or f"{int(time.time() * 1000)}{secrets.randbelow(10**9):09d}"
    signature = hmac.new(secret_key.encode(), (rnd + path + body).encode(), hashlib.sha256).hexdigest()
    raw = f"apiKey:{api_key}&randomKey:{rnd}&signature:{signature}"
    return {
        "Authorization": "IYZWSv2 " + base64.b64encode(raw.encode()).decode(),
        "x-iyzi-rnd": rnd,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def webhook_signature(merchant_id: str, secret_key: str, event_type: str,
                      subscription_ref: str, order_ref: str, customer_ref: str) -> str:
    message = merchant_id + secret_key + event_type + subscription_ref + order_ref + customer_ref
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()


def _ms(value: Any) -> datetime | None:
    if value in (None, "", 0):
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def _period_end(item: dict[str, Any]) -> datetime | None:
    ends = [_ms(o.get("endPeriod")) for o in item.get("orders") or []
            if o.get("orderStatus") == "SUCCESS"]
    ends = [e for e in ends if e]
    return max(ends) if ends else None


class IyzicoProvider:
    name = "iyzico"

    def __init__(self, api_key: str, secret_key: str, base_url: str, merchant_id: str = "",
                 require_webhook_signature: bool = True,
                 client: httpx.Client | None = None) -> None:
        if not api_key or not secret_key:
            raise PaymentError("Ödeme altyapısı yapılandırılmamış (iyzico anahtarları eksik)")
        self.api_key = api_key
        self.secret_key = secret_key
        self.merchant_id = merchant_id
        self.require_webhook_signature = require_webhook_signature
        self.client = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=20.0)

    # --- HTTP -----------------------------------------------------------------
    def _request(self, method: str, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")) if data is not None else ""
        headers = auth_headers(self.api_key, self.secret_key, path, body)
        try:
            resp = self.client.request(method, path, content=body.encode() if body else None,
                                       headers=headers)
        except httpx.HTTPError as exc:
            logger.error("iyzico bağlantı hatası: %s %s: %s", method, path, exc.__class__.__name__)
            raise PaymentError("Ödeme altyapısına ulaşılamadı. Lütfen daha sonra tekrar deneyin.") from exc
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        if resp.status_code >= 400 or payload.get("status") != "success":
            # Kişisel veri içerebileceği için istek gövdesi loglanmaz
            logger.error("iyzico hata: %s %s -> %s %s", method, path, resp.status_code,
                         payload.get("errorCode"))
            msg = payload.get("errorMessage") or "Ödeme işlemi tamamlanamadı."
            raise PaymentError(msg)
        return payload

    # --- Abonelik ---------------------------------------------------------------
    def start_checkout(self, billing: BillingInfo, plan_reference_code: str,
                       callback_url: str, conversation_id: str) -> CheckoutSession:
        if not plan_reference_code:
            raise PaymentError("Ödeme planı yapılandırılmamış")
        contact = f"{billing.name} {billing.surname}"
        data = {
            "locale": "tr",
            "conversationId": conversation_id,
            "callbackUrl": callback_url,
            "pricingPlanReferenceCode": plan_reference_code,
            "subscriptionInitialStatus": "ACTIVE",
            "customer": {
                "name": billing.name,
                "surname": billing.surname,
                "email": billing.email,
                "gsmNumber": billing.gsm_number,
                "identityNumber": billing.identity_number,
                "billingAddress": {
                    "contactName": contact,
                    "city": billing.city,
                    "country": billing.country,
                    "address": billing.address,
                },
            },
        }
        r = self._request("POST", "/v2/subscription/checkoutform/initialize", data)
        return CheckoutSession(token=r["token"], checkout_form_content=r["checkoutFormContent"],
                               expires_in_seconds=r.get("tokenExpireTime"))

    def retrieve_checkout(self, token: str) -> SubscriptionInfo:
        r = self._request("GET", f"/v2/subscription/checkoutform/{token}")
        ref = (r.get("data") or {}).get("referenceCode")
        if not ref:
            raise PaymentError("Ödeme sonucu alınamadı")
        # Dönem bilgisi için abonelik ayrıntısı sorgulanır
        return self.get_subscription(ref)

    def get_subscription(self, reference_code: str) -> SubscriptionInfo:
        r = self._request("GET", f"/v2/subscription/subscriptions/{reference_code}")
        items = (r.get("data") or {}).get("items") or []
        item = next((i for i in items if i.get("referenceCode") == reference_code), None)
        if item is None:
            raise PaymentError("Abonelik bulunamadı")
        return SubscriptionInfo(
            reference_code=reference_code,
            customer_reference_code=item.get("customerReferenceCode"),
            status=STATUS_MAP.get(item.get("subscriptionStatus", ""), SubscriptionStatus.PAST_DUE),
            plan_reference_code=item.get("pricingPlanReferenceCode"),
            current_period_end=_period_end(item),
        )

    def cancel(self, reference_code: str) -> None:
        self._request("POST", f"/v2/subscription/subscriptions/{reference_code}/cancel", {})

    def parse_webhook(self, payload: dict, headers: dict[str, str]) -> WebhookEvent:
        try:
            event = WebhookEvent(
                event_type=str(payload["iyziEventType"]),
                subscription_reference_code=str(payload["subscriptionReferenceCode"]),
                order_reference_code=str(payload.get("orderReferenceCode") or ""),
                customer_reference_code=str(payload.get("customerReferenceCode") or ""),
            )
        except (KeyError, TypeError) as exc:
            raise PaymentError("Geçersiz bildirim") from exc
        given = {k.lower(): v for k, v in headers.items()}.get("x-iyz-signature-v3")
        if given is None:
            if self.require_webhook_signature:
                raise PaymentError("Bildirim imzası yok")
            return event
        expected = webhook_signature(
            self.merchant_id, self.secret_key, event.event_type,
            event.subscription_reference_code, event.order_reference_code or "",
            event.customer_reference_code or "",
        )
        if not hmac.compare_digest(expected.lower(), given.strip().lower()):
            raise PaymentError("Bildirim imzası geçersiz")
        return event
