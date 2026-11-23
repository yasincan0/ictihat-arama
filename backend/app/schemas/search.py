"""Arama ve karar şemaları."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

QUERY_MIN = 30
QUERY_MAX = 5000


class SearchRequest(BaseModel):
    olay: str = Field(max_length=QUERY_MAX)

    @field_validator("olay")
    @classmethod
    def _len(cls, v: str) -> str:
        v = v.strip()
        if len(v) < QUERY_MIN:
            raise ValueError(f"Olayı en az {QUERY_MIN} karakterle anlatın")
        return v


class DecisionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mahkeme: str
    kurul: str | None
    esas_no: str | None
    karar_no: str | None
    karar_tarihi: date | None
    resmi_gazete_tarihi: date | None
    resmi_gazete_sayisi: str | None
    kategori: str | None
    ozet: str | None
    durum: str
    dogrulandi: bool
    dogrulama_kaynagi: str | None

    @field_validator("durum", mode="before")
    @classmethod
    def _durum(cls, v):
        return getattr(v, "value", v)


class DecisionDetail(DecisionSummary):
    tam_metin: str | None
    notlar: list


class SearchResult(BaseModel):
    karar: DecisionSummary
    skor: float
    aciklama: str | None = None
    alinti: str | None = None
    # Claude'un değerlendirmesi: True uygun, False uygun değil, None değerlendirilmedi
    uygun: bool | None = None


class SearchResponse(BaseModel):
    sonuclar: list[SearchResult]
    ornek_veri: bool = False
    # "tamam" | "kapali" (API anahtarı yok) | "hata"
    aciklama_durumu: str
    genel_degerlendirme: str | None = None


class PublicConfig(BaseModel):
    arama_giris_gerekli: bool
    abonelik_acik: bool
    aciklama_acik: bool
    karar_sayisi: int
    dogrulanmis_karar_sayisi: int
