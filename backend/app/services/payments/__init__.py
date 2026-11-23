"""Ödeme modülü. Sağlayıcı ayarlardan (PAYMENT_PROVIDER) seçilir."""

from functools import lru_cache

from app.core.config import get_settings
from app.services.payments.base import (
    BillingInfo,
    CheckoutSession,
    PaymentError,
    PaymentProvider,
    SubscriptionInfo,
    WebhookEvent,
)


@lru_cache
def _fake_provider():
    from app.services.payments.fake import FakeProvider

    return FakeProvider()


def get_payment_provider() -> PaymentProvider:
    """FastAPI bağımlılığı. Testlerde dependency_overrides ile değiştirilir."""
    s = get_settings()
    if s.payment_provider == "iyzico":
        from app.services.payments.iyzico import IyzicoProvider

        return IyzicoProvider(s.iyzico_api_key, s.iyzico_secret_key, s.iyzico_base_url,
                              s.iyzico_merchant_id, s.iyzico_webhook_require_signature)
    if s.payment_provider == "fake":
        if s.app_env == "production":
            raise RuntimeError("Üretimde PAYMENT_PROVIDER=fake kullanılamaz")
        return _fake_provider()
    raise RuntimeError(f"Bilinmeyen PAYMENT_PROVIDER: {s.payment_provider}")


__all__ = [
    "BillingInfo",
    "CheckoutSession",
    "PaymentError",
    "PaymentProvider",
    "SubscriptionInfo",
    "WebhookEvent",
    "get_payment_provider",
]
