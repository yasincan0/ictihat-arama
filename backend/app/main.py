"""FastAPI uygulamasının giriş noktası."""

import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.payments import router as payments_router
from app.api.search import router as search_router
from app.core.config import Settings, get_settings
from app.core.logging import install_redaction
from app.core.middleware import (
    BodySizeLimitMiddleware,
    OriginCheckMiddleware,
    SecurityHeadersMiddleware,
)


def check_production_settings(settings: Settings) -> None:
    """Üretimde güvensiz varsayılanlarla açılmayı engeller."""
    if settings.app_env != "production":
        return
    problems = []
    if settings.secret_key in ("gelistirme-anahtari-yalnizca-yerel-kullanim-icindir",
                               "uzun-rastgele-bir-deger-uretin") \
            or len(settings.secret_key) < 32:
        problems.append("SECRET_KEY en az 32 karakterlik rastgele bir değer olmalı")
    if not settings.cookie_secure:
        problems.append("COOKIE_SECURE=true olmalı")
    if settings.email_backend == "console":
        problems.append("EMAIL_BACKEND=console üretimde kullanılamaz")
    if settings.payments_enabled and settings.payment_provider == "fake":
        problems.append("PAYMENT_PROVIDER=fake üretimde kullanılamaz")
    if settings.payments_enabled and settings.payment_provider == "iyzico" and "sandbox" in settings.iyzico_base_url:
        problems.append("Üretimde iyzico sandbox adresi kullanılamaz")
    if "*" in settings.cors_origin_list:
        problems.append("CORS_ORIGINS '*' olamaz (çerezli oturum)")
    if any(o.startswith("http://") for o in settings.cors_origin_list):
        problems.append("CORS_ORIGINS üretimde https olmalı")
    if problems:
        raise RuntimeError("Üretim ayarları hatalı: " + "; ".join(problems))


def _warm_up_embedder() -> None:
    """Embedding modelini arka planda belleğe yükler; ilk arama beklemesin."""
    from app.services.embedding import get_embedder

    try:
        get_embedder().encode_query("ısınma")
    except Exception:  # model sorunları ilk aramada görünür; açılışı engellemesin
        logging.getLogger(__name__).exception("Embedding modeli ısıtılamadı")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().embedding_backend == "sentence-transformers":
        threading.Thread(target=_warm_up_embedder, daemon=True).start()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    check_production_settings(settings)
    app = FastAPI(title="İçtihat Arama API", version="0.1.0", lifespan=lifespan)
    install_redaction()
    # Sıra: en son eklenen en dışta çalışır.
    app.add_middleware(OriginCheckMiddleware, settings=settings)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
        max_age=600,
    )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(payments_router)
    app.include_router(search_router)
    return app


app = create_app()
