"""Uygulama ayarları. Değerler ortam değişkenlerinden veya .env dosyasından okunur."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://ictihat:degistir@localhost:5432/ictihat"
    secret_key: str = "gelistirme-anahtari-yalnizca-yerel-kullanim-icindir"
    cors_origins: str = "http://localhost:3000"

    # Embedding modeli değiştirilebilir; boyut migration ve modellerde buradan okunur.
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = Field(default=1024, gt=0)

    # --- Oturum ve üyelik ---
    # Oturum çerezi (HttpOnly, SameSite=Lax). Üretimde cookie_secure=true olmalı.
    session_cookie_name: str = "ictihat_oturum"
    session_ttl_minutes: int = Field(default=60 * 24 * 7, gt=0)
    cookie_secure: bool = False
    jwt_algorithm: str = "HS256"
    email_verify_ttl_hours: int = Field(default=48, gt=0)
    password_reset_ttl_minutes: int = Field(default=60, gt=0)
    # E-postalardaki bağlantılar bu adrese göre üretilir
    frontend_url: str = "http://localhost:3000"
    # "console": geliştirmede e-postaları günlüğe yazar (üretimde kullanılamaz)
    email_backend: str = "console"
    email_from: str = "İçtihat Arama <no-reply@localhost>"
    # Aboneliği olmayan kullanıcının aylık ücretsiz arama hakkı
    free_searches_per_month: int = Field(default=3, ge=0)
    # Kota ayı bu saat dilimine göre hesaplanır
    quota_timezone: str = "Europe/Istanbul"

    # --- Ödeme / abonelik ---
    # "fake": geliştirme ve test için sahte sağlayıcı; "iyzico": gerçek (sandbox veya canlı)
    payment_provider: str = "fake"
    # iyzico'nun ödeme sonucunu döndüreceği arka uç adresi (dışarıdan erişilebilir olmalı)
    backend_url: str = "http://localhost:8000"
    iyzico_api_key: str = ""
    iyzico_secret_key: str = ""
    iyzico_base_url: str = "https://sandbox-api.iyzipay.com"
    # Webhook imzası (X-IYZ-SIGNATURE-V3) hesaplamasında kullanılır
    iyzico_merchant_id: str = ""
    # iyzico panelinde tanımlı aylık ödeme planının referans kodu
    iyzico_plan_reference_code: str = ""
    iyzico_webhook_require_signature: bool = True
    # Arayüzde gösterilecek fiyat metni, ör. "Aylık 499 TL (KDV dahil)"
    subscription_price_text: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
