"""E-posta gönderici arayüzü ve geliştirme/test uygulamaları."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Yalnızca geliştirme: e-postayı günlüğe yazar (bağlantıları elle açabilmek için)."""

    def send(self, message: EmailMessage) -> None:
        logger.warning(
            "[GELİŞTİRME E-POSTASI] Kime: %s | Konu: %s\n%s",
            message.to,
            message.subject,
            message.body,
        )


class MemoryEmailSender:
    """Testler için: gönderilen e-postaları bellekte tutar."""

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)
