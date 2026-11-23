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
    secret_key: str = "gelistirme-anahtari"
    cors_origins: str = "http://localhost:3000"

    # Embedding modeli değiştirilebilir; boyut migration ve modellerde buradan okunur.
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = Field(default=1024, gt=0)

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
