"""Geliştirme ve testler için sahte ödeme sağlayıcısı. Gerçek ödeme almaz.

Ödeme formu yerine, callback adresine "başarılı ödeme" gönderen bir buton üretir.
Üretimde kullanılamaz (bkz. app.main.check_production_settings)."""

from __future__ import annotations

import html
import secrets
from datetime import datetime, timedelta, timezone

from app.models import SubscriptionStatus
from app.services.payments.base import (
    BillingInfo,
    CheckoutSession,
    PaymentError,
    SubscriptionInfo,
    WebhookEvent,
)


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.checkouts: dict[str, str] = {}  # token -> abonelik ref
        self.subscriptions: dict[str, SubscriptionInfo] = {}
        self.canceled: list[str] = []
        self.last_billing: BillingInfo | None = None

    def start_checkout(self, billing: BillingInfo, plan_reference_code: str,
                       callback_url: str, conversation_id: str) -> CheckoutSession:
        self.last_billing = billing
        token = "fake-" + secrets.token_urlsafe(12)
        ref = "fake-sub-" + secrets.token_hex(6)
        self.checkouts[token] = ref
        self.subscriptions[ref] = SubscriptionInfo(
            reference_code=ref,
            customer_reference_code="fake-cus-" + secrets.token_hex(4),
            status=SubscriptionStatus.ACTIVE,
            plan_reference_code=plan_reference_code or "fake-plan",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        )
        form = (
            f'<form method="post" action="{html.escape(callback_url)}">'
            f'<input type="hidden" name="token" value="{html.escape(token)}">'
            '<p>Geliştirme modu: gerçek ödeme alınmaz.</p>'
            '<button type="submit">Ödemeyi tamamla (sahte)</button></form>'
        )
        return CheckoutSession(token=token, checkout_form_content=form, expires_in_seconds=1800)

    def retrieve_checkout(self, token: str) -> SubscriptionInfo:
        ref = self.checkouts.get(token)
        if ref is None:
            raise PaymentError("Ödeme sonucu alınamadı")
        return self.subscriptions[ref]

    def get_subscription(self, reference_code: str) -> SubscriptionInfo:
        if reference_code not in self.subscriptions:
            raise PaymentError("Abonelik bulunamadı")
        return self.subscriptions[reference_code]

    def cancel(self, reference_code: str) -> None:
        info = self.get_subscription(reference_code)
        self.canceled.append(reference_code)
        self.subscriptions[reference_code] = SubscriptionInfo(
            reference_code, info.customer_reference_code, SubscriptionStatus.CANCELED,
            info.plan_reference_code, info.current_period_end,
        )

    def parse_webhook(self, payload: dict, headers: dict[str, str]) -> WebhookEvent:
        if headers.get("x-fake-signature") != "gecerli":
            raise PaymentError("Bildirim imzası geçersiz")
        return WebhookEvent(payload["iyziEventType"], payload["subscriptionReferenceCode"],
                            payload.get("orderReferenceCode"), payload.get("customerReferenceCode"))
