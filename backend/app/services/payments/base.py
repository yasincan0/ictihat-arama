"""Ödeme sağlayıcı arayüzü. Uygulamanın geri kalanı yalnızca bu tipleri kullanır;
iyzico'ya özgü ayrıntılar iyzico.py içinde kalır."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models import SubscriptionStatus


class PaymentError(RuntimeError):
    """Sağlayıcı isteği başarısız oldu. Mesaj kullanıcıya gösterilebilir (Türkçe)."""


@dataclass(frozen=True)
class BillingInfo:
    """Ödeme kuruluşunun istediği fatura bilgileri. Sağlayıcıya iletilir, bizde SAKLANMAZ."""

    name: str
    surname: str
    email: str
    gsm_number: str  # +905xxxxxxxxx
    identity_number: str  # TC kimlik no
    address: str
    city: str
    country: str = "Turkey"


@dataclass(frozen=True)
class CheckoutSession:
    token: str
    checkout_form_content: str  # sağlayıcının ödeme formu (HTML + script)
    expires_in_seconds: int | None


@dataclass(frozen=True)
class SubscriptionInfo:
    reference_code: str
    customer_reference_code: str | None
    status: SubscriptionStatus
    plan_reference_code: str | None
    # Ödemesi yapılmış son dönemin bitişi (bilinmiyorsa None)
    current_period_end: datetime | None


@dataclass(frozen=True)
class WebhookEvent:
    event_type: str
    subscription_reference_code: str
    order_reference_code: str | None
    customer_reference_code: str | None


class PaymentProvider(Protocol):
    name: str

    def start_checkout(self, billing: BillingInfo, plan_reference_code: str,
                       callback_url: str, conversation_id: str) -> CheckoutSession: ...

    def retrieve_checkout(self, token: str) -> SubscriptionInfo: ...

    def get_subscription(self, reference_code: str) -> SubscriptionInfo: ...

    def cancel(self, reference_code: str) -> None: ...

    def parse_webhook(self, payload: dict, headers: dict[str, str]) -> WebhookEvent:
        """İmzayı doğrular ve olayı döndürür; geçersizse PaymentError."""
        ...
