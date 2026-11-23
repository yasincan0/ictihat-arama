"""Kullanıcıya giden e-posta metinleri (Türkçe)."""

from app.core.config import Settings
from app.services.email.base import EmailMessage


def verify_email(to: str, token: str, settings: Settings) -> EmailMessage:
    link = f"{settings.frontend_url.rstrip('/')}/eposta-dogrula?jeton={token}"
    return EmailMessage(
        to=to,
        subject="E-posta adresinizi doğrulayın",
        body=(
            "Merhaba,\n\nİçtihat Arama hesabınızı etkinleştirmek için aşağıdaki bağlantıyı "
            f"açın:\n\n{link}\n\nBağlantı {settings.email_verify_ttl_hours} saat geçerlidir. "
            "Bu kaydı siz yapmadıysanız bu e-postayı dikkate almayın.\n"
        ),
    )


def account_exists(to: str, settings: Settings) -> EmailMessage:
    link = f"{settings.frontend_url.rstrip('/')}/sifremi-unuttum"
    return EmailMessage(
        to=to,
        subject="Bu e-posta adresiyle zaten bir hesabınız var",
        body=(
            "Merhaba,\n\nBu e-posta adresiyle yeniden kayıt olunmaya çalışıldı, ancak "
            "zaten bir hesabınız var. Şifrenizi hatırlamıyorsanız şu bağlantıdan "
            f"sıfırlayabilirsiniz:\n\n{link}\n\nBu işlemi siz yapmadıysanız bu e-postayı "
            "dikkate almayın.\n"
        ),
    )


def reset_password(to: str, token: str, settings: Settings) -> EmailMessage:
    link = f"{settings.frontend_url.rstrip('/')}/sifre-sifirla?jeton={token}"
    return EmailMessage(
        to=to,
        subject="Şifre sıfırlama",
        body=(
            "Merhaba,\n\nŞifrenizi sıfırlamak için aşağıdaki bağlantıyı açın:\n\n"
            f"{link}\n\nBağlantı {settings.password_reset_ttl_minutes} dakika geçerlidir ve "
            "yalnızca bir kez kullanılabilir. Bu isteği siz yapmadıysanız şifreniz "
            "değişmez; bu e-postayı dikkate almayın.\n"
        ),
    )
