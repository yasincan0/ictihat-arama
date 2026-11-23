"""FastAPI uygulamasının giriş noktası."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.payments import router as payments_router
from app.core.config import Settings, get_settings


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
    if settings.payment_provider == "fake":
        problems.append("PAYMENT_PROVIDER=fake üretimde kullanılamaz")
    if settings.payment_provider == "iyzico" and "sandbox" in settings.iyzico_base_url:
        problems.append("Üretimde iyzico sandbox adresi kullanılamaz")
    if problems:
        raise RuntimeError("Üretim ayarları hatalı: " + "; ".join(problems))


def create_app() -> FastAPI:
    settings = get_settings()
    check_production_settings(settings)
    app = FastAPI(title="İçtihat Arama API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(payments_router)
    return app


app = create_app()
