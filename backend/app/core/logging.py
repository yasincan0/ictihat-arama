"""Günlük yapılandırması ve kişisel veri maskeleme.

Kural (CLAUDE.md / KVKK): olay metni günlüğe yazılmaz. Kodda olay metni hiçbir zaman
loglanmaz; buna ek olarak bu filtre, yanlışlıkla günlüğe düşebilecek T.C. kimlik no,
telefon ve kart numarası benzeri dizileri maskeler.
"""

from __future__ import annotations

import logging
import re

_PATTERNS = [
    # Kart numarası benzeri 13-19 hane (boşluk/tire ile ayrılmış olabilir)
    (re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), "[KART?]"),
    # T.C. kimlik no: 11 hane
    (re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)"), "[TCKN?]"),
    # Türkiye cep telefonu: +90 5xx..., 05xx...
    (re.compile(r"(?:\+?90|0)?\s?5\d{2}\s?\d{3}\s?\d{2}\s?\d{2}\b"), "[TEL?]"),
]


def redact(text: str) -> str:
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # biçimlendirme hatası: kaydı olduğu gibi bırak
            return True
        cleaned = redact(message)
        if cleaned != message:
            record.msg, record.args = cleaned, None
        return True


_installed = False


def install_redaction() -> None:
    """Maskelemeyi kayıt fabrikasına ekler: hangi günlükçü veya işleyici kullanılırsa
    kullanılsın, her günlük kaydı oluşturulurken maskelenir."""
    global _installed
    if _installed:
        return
    previous = logging.getLogRecordFactory()
    flt = RedactingFilter()

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        flt.filter(record)
        return record

    logging.setLogRecordFactory(factory)
    _installed = True
