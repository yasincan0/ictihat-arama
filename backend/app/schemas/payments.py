"""Abonelik/ödeme şemaları."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def is_valid_tckn(value: str) -> bool:
    """T.C. kimlik numarası algoritma denetimi (11 hane, ilk hane 0 değil, iki denetim hanesi)."""
    if not re.fullmatch(r"[1-9]\d{10}", value):
        return False
    d = [int(c) for c in value]
    d10 = (sum(d[0:9:2]) * 7 - sum(d[1:8:2])) % 10
    d11 = sum(d[:10]) % 10
    return d[9] == d10 and d[10] == d11


def normalize_tr_gsm(value: str) -> str:
    """05xx..., 5xx..., +90 5xx... biçimlerini +905xxxxxxxxx yapar."""
    digits = re.sub(r"\D", "", value)
    if digits.startswith("90") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if not re.fullmatch(r"5\d{9}", digits):
        raise ValueError("Geçerli bir cep telefonu numarası girin (ör. 0532 123 45 67)")
    return "+90" + digits


class BillingRequest(BaseModel):
    """Ödeme kuruluşunun (iyzico) zorunlu tuttuğu bilgiler. Yalnızca iyzico'ya iletilir."""

    ad: str = Field(min_length=1, max_length=100)
    soyad: str = Field(min_length=1, max_length=100)
    tckn: str = Field(min_length=11, max_length=11)
    telefon: str = Field(min_length=10, max_length=20)
    adres: str = Field(min_length=5, max_length=300)
    sehir: str = Field(min_length=2, max_length=50)

    @field_validator("ad", "soyad", "adres", "sehir")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Bu alan boş olamaz")
        return v

    @field_validator("tckn")
    @classmethod
    def _tckn(cls, v: str) -> str:
        if not is_valid_tckn(v):
            raise ValueError("T.C. kimlik numarası geçersiz")
        return v

    @field_validator("telefon")
    @classmethod
    def _gsm(cls, v: str) -> str:
        return normalize_tr_gsm(v)


class CheckoutResponse(BaseModel):
    token: str
    checkout_form_content: str
    saglayici: str


class SubscriptionResponse(BaseModel):
    var: bool
    durum: str | None = None
    donem_sonu: datetime | None = None
    plan: str | None = None
    iptal_edilebilir: bool = False


class PlanResponse(BaseModel):
    fiyat_metni: str
    saglayici: str
    ucretsiz_arama_hakki: int
