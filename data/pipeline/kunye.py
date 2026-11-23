"""Resmî metinden künye (esas, karar, tarih), Resmî Gazete bilgisi çıkarma ve
listedeki özetle karşılaştırma yardımcıları.

Mahkemeden bağımsızdır; mahkeme/kurul denetimi için anahtar kelimeler parametre olarak verilir.
Buradaki özet karşılaştırması sezgiseldir (kelime kökü örtüşmesi + olumsuzluk denetimi);
hukuki anlam denetiminin yerini tutmaz, yalnızca insan incelemesine yön verir.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from data.pipeline.load_seed import normalize_text

MONTHS = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
}
_MONTH_RE = "|".join(MONTHS)

# "E.1969/2", "Esas No : 1969/2", "Esas Numarası: 1969/2", "E: 1969/2"
ESAS_RE = re.compile(
    r"\b(?:Esas|E)\s*(?:No(?:su)?|Numaras[ıi])?\s*[.:]?\s*:?\s*(\d{4})\s*/\s*(\d{1,5})\b",
    re.IGNORECASE,
)
KARAR_RE = re.compile(
    r"\b(?:Karar|K)\s*(?:No(?:su)?|Numaras[ıi])?\s*[.:]?\s*:?\s*(\d{4})\s*/\s*(\d{1,5})\b",
    re.IGNORECASE,
)
_NUM_DATE = r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})"
_TXT_DATE = rf"(\d{{1,2}})\s+({_MONTH_RE})\s+(\d{{4}})"
KARAR_TARIHI_RE = re.compile(
    rf"Karar\s+(?:Tarihi|Günü|Gün[üu]|T\.)\s*[.:]?\s*:?\s*(?:{_NUM_DATE}|{_TXT_DATE})",
    re.IGNORECASE,
)
# Kararın sonundaki "... 12.2.1970 tarihinde ... karar verildi." kalıbı
TARIHINDE_RE = re.compile(
    rf"(?:{_NUM_DATE}|{_TXT_DATE})\s+(?:günü|tarihinde)[^.]{{0,200}}karar\s+verildi",
    re.IGNORECASE,
)
RG_SAYI_RE = re.compile(r"Say[ıi]\s*[.:]?\s*:?\s*(\d{3,5})\b", re.IGNORECASE)
RG_TARIH_RE = re.compile(rf"(?:{_NUM_DATE}|{_TXT_DATE})", re.IGNORECASE)
# Dosya adı kuralı: ...rg-19700512-13500...  ve isteğe bağlı  sira-5
FILENAME_RG_RE = re.compile(r"rg[-_](\d{8})[-_](\d{3,5})", re.IGNORECASE)
FILENAME_SIRA_RE = re.compile(r"sira[-_](\d{1,4})", re.IGNORECASE)


def _lower_tr(text: str) -> str:
    return unicodedata.normalize("NFC", text).replace("İ", "i").replace("I", "ı").lower()


def _to_date(groups: tuple[str | None, ...]) -> date | None:
    """_NUM_DATE veya _TXT_DATE eşleşme gruplarından tarih üretir (6 grup)."""
    d, m, y, td, tm, ty = groups
    try:
        if d:
            return date(int(y), int(m), int(d))
        if td:
            return date(int(ty), MONTHS[_lower_tr(tm)], int(td))
    except (ValueError, KeyError):
        return None
    return None


def _no(match: re.Match) -> str:
    return f"{int(match.group(1))}/{int(match.group(2))}"


@dataclass
class ParsedKunye:
    esas_no: str | None
    karar_no: str | None
    # Metindeki konumu (bölümlere ayırmak için)
    start: int
    karar_tarihi: date | None = None
    segment: str = ""


@dataclass
class RgInfo:
    tarih: date | None = None
    sayi: str | None = None
    kaynak: str | None = None  # "dosya_adi" veya "metin"


# Esas numarasından sonra karar numarasının aranacağı en fazla uzaklık (karakter)
PAIR_DISTANCE = 200
# Bir bölüm, künyesinden bu kadar önce başlayabilir (kurul adı, başlık vb.)
SEGMENT_LEAD = 300


def find_kunye_candidates(text: str) -> list[ParsedKunye]:
    """Metindeki tüm (esas, karar) çiftlerini sırayla döndürür.

    İBK kararları, aralarındaki aykırılık giderilen daire kararlarına da "E./K." ile
    atıf yapar; bu yüzden burada bulunan her çift karar başlığı değildir. Hangisinin
    aranan karar olduğuna veritabanıyla eşleştirme aşamasında karar verilir.
    """
    out: list[ParsedKunye] = []
    seen: set[tuple[str | None, str | None]] = set()
    for m in ESAS_RE.finditer(text):
        km = KARAR_RE.search(text, m.end(), min(len(text), m.end() + PAIR_DISTANCE))
        key = (_no(m), _no(km) if km else None)
        if key in seen:
            continue
        seen.add(key)
        out.append(ParsedKunye(esas_no=key[0], karar_no=key[1], start=m.start()))
    if not out:
        # Esas numarası okunamadıysa (ör. OCR hatası) yalnızca karar numaraları
        for km in KARAR_RE.finditer(text):
            key = (None, _no(km))
            if key not in seen:
                seen.add(key)
                out.append(ParsedKunye(esas_no=None, karar_no=key[1], start=km.start()))
    return out


def assign_segments(text: str, kunyeler: list[ParsedKunye]) -> list[ParsedKunye]:
    """Verilen künyeleri (yalnızca aranan kararlar) metin bölümlerine ayırır ve her
    bölümden karar tarihini okur. Tek künye varsa bölüm metnin tamamıdır."""
    ordered = sorted(kunyeler, key=lambda k: k.start)
    for i, k in enumerate(ordered):
        seg_start = 0 if i == 0 else max(ordered[i - 1].start + 1, k.start - SEGMENT_LEAD)
        seg_end = ordered[i + 1].start - SEGMENT_LEAD if i + 1 < len(ordered) else len(text)
        seg_end = max(seg_end, k.start + 1)
        k.segment = text[seg_start:seg_end]
        k.karar_tarihi = find_karar_tarihi(k.segment)
    return ordered


def find_karar_tarihi(text: str) -> date | None:
    m = KARAR_TARIHI_RE.search(text)
    if m and (d := _to_date(m.groups())):
        return d
    matches = list(TARIHINDE_RE.finditer(text))
    if matches:
        return _to_date(matches[-1].groups()[:6])
    return None


def parse_rg_from_filename(name: str) -> RgInfo:
    m = FILENAME_RG_RE.search(name)
    if not m:
        return RgInfo()
    raw = m.group(1)
    try:
        tarih = date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
    except ValueError:
        return RgInfo()
    return RgInfo(tarih=tarih, sayi=str(int(m.group(2))), kaynak="dosya_adi")


def parse_rg_from_text(text: str) -> RgInfo:
    """Resmî Gazete başlığındaki tarih ve sayıyı metnin başından okur."""
    head = text[:2000]
    if "gazete" not in _lower_tr(head):
        return RgInfo()
    sayi = RG_SAYI_RE.search(head)
    tarih = None
    for m in RG_TARIH_RE.finditer(head):
        if d := _to_date(m.groups()):
            tarih = d
            break
    if not sayi or not tarih:
        return RgInfo()
    return RgInfo(tarih=tarih, sayi=str(int(sayi.group(1))), kaynak="metin")


def parse_sira_from_filename(name: str) -> int | None:
    m = FILENAME_SIRA_RE.search(name)
    return int(m.group(1)) if m else None


def mentions_all(text: str, keyword_groups: list[list[str]]) -> bool:
    """Her gruptan en az bir anahtar kelime metinde geçiyor mu (Türkçe küçük harf)?"""
    low = _lower_tr(text)
    return all(any(_lower_tr(k) in low for k in group) for group in keyword_groups)


# --- Özet karşılaştırma -----------------------------------------------------------

STOPWORDS = {
    "ve", "ile", "bir", "bu", "şu", "için", "olan", "olarak", "da", "de", "ki", "veya",
    "ya", "ise", "gibi", "daha", "her", "çok", "en", "ne", "o", "göre", "kadar", "sonra",
    "önce", "üzere", "ancak", "fakat", "ama",
}
STEM_LEN = 5

# Olumsuzluk belirteçleri (sezgisel): -maz/-mez, -mamak, -madığı, değil, yok ...
NEGATION_RE = re.compile(
    r"\b\w*(?:maz|mez|mamak\w*|memek\w*|madığ\w*|mediğ\w*|mamış\w*|memiş\w*|mayac\w*|"
    r"meyec\w*|mamas\w*|memes\w*|amaz|emez|amayac\w*|emeyec\w*)\b|\bdeğil\w*|\byok\w*|"
    r"\baranmaz\b",
)


def stems(text: str) -> list[str]:
    tokens = normalize_text(text).split()
    out = []
    for t in tokens:
        if t in STOPWORDS:
            continue
        if t.isdigit():
            out.append(t)
        elif len(t) >= 3:
            out.append(t[:STEM_LEN])
    return out


def has_negation(text: str) -> bool:
    return bool(NEGATION_RE.search(_lower_tr(text)))


_SENTENCE_SPLIT = re.compile(r"(?<=[.;:!?])\s+|\n{2,}")


@dataclass
class SummaryMatch:
    # Özetteki kelime köklerinin resmî metinde (tamamında) bulunma oranı
    coverage: float
    # En iyi örtüşen pasajdaki (en fazla 3 cümle) oran
    window_coverage: float
    passage: str
    negation_mismatch: bool
    missing: list[str] = field(default_factory=list)


def compare_summary(summary: str, text: str, window: int = 3) -> SummaryMatch:
    want = set(stems(summary))
    if not want:
        return SummaryMatch(0.0, 0.0, "", False)
    text_stems = set(stems(text))
    found = want & text_stems
    coverage = len(found) / len(want)

    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]
    sent_stems = [set(stems(s)) for s in sentences]
    best_cov, best_idx, best_len = -1.0, 0, 1
    for i in range(len(sentences)):
        acc: set[str] = set()
        for n in range(1, window + 1):
            if i + n > len(sentences):
                break
            acc |= sent_stems[i + n - 1]
            cov = len(want & acc) / len(want)
            # Eşit kapsamda daha kısa pasajı tercih et
            if cov > best_cov + 1e-9:
                best_cov, best_idx, best_len = cov, i, n
    passage = " ".join(sentences[best_idx : best_idx + best_len]) if sentences else ""
    negation_mismatch = bool(passage) and has_negation(summary) != has_negation(passage)

    # Eksik kökleri özetteki ilk geçtikleri biçimiyle göster
    missing_words = []
    for tok in normalize_text(summary).split():
        st = tok if tok.isdigit() else tok[:STEM_LEN]
        if st in want - found and tok not in missing_words:
            missing_words.append(tok)
    return SummaryMatch(
        coverage=round(coverage, 3),
        window_coverage=round(max(best_cov, 0.0), 3),
        passage=passage,
        negation_mismatch=negation_mismatch,
        missing=missing_words,
    )
