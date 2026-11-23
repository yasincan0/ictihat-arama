"""E-posta gönderimi. Uygulama yalnızca EmailSender arayüzünü kullanır; gerçek sağlayıcı
(SMTP, SES vb.) eklemek için yeni bir sınıf yazıp get_email_sender içinde seçmek yeterlidir."""

from app.services.email.base import ConsoleEmailSender, EmailMessage, EmailSender, MemoryEmailSender
from app.services.email.sender import get_email_sender

__all__ = [
    "ConsoleEmailSender",
    "EmailMessage",
    "EmailSender",
    "MemoryEmailSender",
    "get_email_sender",
]
