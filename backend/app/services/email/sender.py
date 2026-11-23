from app.core.config import get_settings
from app.services.email.base import ConsoleEmailSender, EmailSender


def get_email_sender() -> EmailSender:
    """FastAPI bağımlılığı. Testlerde dependency_overrides ile değiştirilir."""
    settings = get_settings()
    if settings.email_backend == "console":
        if settings.app_env == "production":
            raise RuntimeError("Üretimde EMAIL_BACKEND=console kullanılamaz")
        return ConsoleEmailSender()
    raise RuntimeError(f"Bilinmeyen EMAIL_BACKEND: {settings.email_backend}")
