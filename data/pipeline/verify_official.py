"""Elle indirilen resmî metinlerle (Resmî Gazete) kararların künyesini ve özetini doğrular.

Kullanım (depo kökünden):
    python -m data.pipeline.verify_official            # data/raw/resmigazete/ altını işle
    python -m data.pipeline.verify_official --dry-run  # veritabanına yazmadan dene
    python -m data.pipeline.verify_official --force    # daha önce işlenen dosyaları da yeniden işle
    python -m data.pipeline.verify_official --liste    # docs/indirilecekler.md listesini üret

Dosya adı kuralı (önerilir, zorunlu değil):
    rg-YYYYMMDD-SAYI[_sira-N].pdf     ör. rg-19700512-13500_sira-5.pdf
Resmî Gazete tarih/sayısı dosya adında yoksa metnin başlığından okunmaya çalışılır.
`sira-N` verilirse dosya listedeki o kayıtla eşleştirilir (künye OCR ile okunamazsa işe yarar).

Her dosya için:
1. Metin çıkarılır (gerekirse OCR; sonuç data/processed/metin/ altında önbellekte).
2. Metindeki (esas, karar) çiftleri bulunur ve veritabanındaki kararlarla eşleştirilir.
3. Künye (esas, karar, karar tarihi), Resmî Gazete tarih/sayısı ve kurul adı denetlenir;
   listedeki özet resmî metinle karşılaştırılır.
4. Tüm denetimlerden geçen kararlar dogrulandi=true yapılır; diğerleri raporlanır.
   Daha önce doğrulanmış kayıtlara dokunulmaz.

İşlenen dosyalar data/processed/dogrulama/sonuclar.json içine yazılır; tekrar
çalıştırıldığında yalnızca yeni dosyalar işlenir (kaldığı yerden devam).
Rapor her çalıştırmada docs/dogrulama_raporu.md olarak baştan üretilir.
"""

from __future__ import annotations

import argparse
import enum
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from data.pipeline import _bootstrap  # noqa: F401  (app.* içe aktarımı için)
from data.pipeline.kunye import (
    ParsedKunye,
    RgInfo,
    assign_segments,
    compare_summary,
    find_kunye_candidates,
    mentions_all,
    parse_rg_from_filename,
    parse_rg_from_text,
    parse_sira_from_filename,
)
from data.pipeline.load_seed import DEFAULT_SEED_FILE
from data.pipeline.text_extract import (
    SUPPORTED_SUFFIXES,
    ExtractionError,
    ExtractedText,
    extract_text,
)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models import Decision  # noqa: E402

REPO_ROOT = _bootstrap.REPO_ROOT
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw" / "resmigazete"
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "processed" / "metin"
DEFAULT_STATE_FILE = REPO_ROOT / "data" / "processed" / "dogrulama" / "sonuclar.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "dogrulama_raporu.md"
DEFAULT_DOWNLOAD_LIST = REPO_ROOT / "docs" / "indirilecekler.md"

PILOT_SIZE = 10

# Özet karşılaştırma eşikleri (bkz. kunye.compare_summary)
COVERAGE_OK = 0.70  # bunun üstü: özet resmî metinle uyuşuyor
COVERAGE_MIN = 0.50  # bunun altı: uyuşmuyor; arası: incelenmeli
WINDOW_OK = 0.50  # en iyi pasajdaki oran bunun altındaysa incelenmeli

# Mahkemeye özgü denetim bilgileri. Yeni mahkeme eklemek için buraya bir giriş yeterli.
COURT_PROFILES: dict[str, dict[str, Any]] = {
    "Danıştay": {
        "kaynak_adi": "Resmî Gazete",
        # Her gruptan en az bir ifade metinde geçmeli
        "keywords": [["danıştay"], ["birleştirme", "tevhid"]],
    },
}


class Outcome(str, enum.Enum):
    DOGRULANDI = "dogrulandi"
    INCELENMELI = "incelenmeli"
    UYUSMUYOR = "uyusmuyor"
    KORUNDU = "korundu"  # zaten doğrulanmış; dokunulmadı
    ESLESMEDI = "eslesmedi"  # dosyadaki hiçbir künye listedeki bir kararla eşleşmedi
    METIN_YOK = "metin_yok"  # dosyadan metin çıkarılamadı


OUTCOME_LABELS = {
    Outcome.DOGRULANDI: "Doğrulandı",
    Outcome.INCELENMELI: "İncelenmeli",
    Outcome.UYUSMUYOR: "Uyuşmuyor",
    Outcome.KORUNDU: "Zaten doğrulanmış",
    Outcome.ESLESMEDI: "Eşleşmedi",
    Outcome.METIN_YOK: "Metin çıkarılamadı",
}


@dataclass
class Check:
    name: str
    ok: bool | None  # None: denetlenemedi
    detail: str
    hard: bool = False  # başarısızsa "uyuşmuyor" (yoksa "incelenmeli")


@dataclass
class VerificationResult:
    file: str
    sha256: str
    outcome: Outcome
    method: str | None = None
    seed_sira: int | None = None
    decision_id: int | None = None
    liste_kunye: dict[str, Any] = field(default_factory=dict)
    resmi_kunye: dict[str, Any] = field(default_factory=dict)
    rg: dict[str, Any] = field(default_factory=dict)
    checks: list[Check] = field(default_factory=list)
    ozet: str | None = None
    ozet_kapsam: float | None = None
    pasaj_kapsam: float | None = None
    pasaj: str | None = None
    eksik_kelimeler: list[str] = field(default_factory=list)
    diger_kunyeler: list[str] = field(default_factory=list)
    hata: str | None = None

    @property
    def reasons(self) -> list[str]:
        return [c.detail for c in self.checks if c.ok is not True]


# --- Eşleştirme ------------------------------------------------------------------


@dataclass
class _Match:
    kunye: ParsedKunye
    decision: Decision
    weak: bool = False  # yalnızca karar numarasıyla eşleşti


class DecisionIndex:
    def __init__(self, decisions: list[Decision]):
        self.by_ek: dict[tuple[str, str], Decision] = {}
        self.by_k: dict[str, list[Decision]] = {}
        self.by_sira: dict[int, Decision] = {}
        for d in decisions:
            if d.esas_no and d.karar_no:
                self.by_ek[(d.esas_no, d.karar_no)] = d
            if d.karar_no:
                self.by_k.setdefault(d.karar_no, []).append(d)
            if d.seed_sira is not None:
                self.by_sira[d.seed_sira] = d

    @classmethod
    def load(cls, session: Session, mahkeme: str) -> "DecisionIndex":
        return cls(list(session.scalars(select(Decision).where(Decision.mahkeme == mahkeme))))


def match_candidates(
    candidates: list[ParsedKunye], index: DecisionIndex, forced_sira: int | None
) -> list[_Match]:
    matches: list[_Match] = []
    used: set[int] = set()

    def add(k: ParsedKunye, d: Decision, weak: bool = False) -> None:
        if id(d) not in used:
            used.add(id(d))
            matches.append(_Match(k, d, weak))

    for k in candidates:
        if k.esas_no and k.karar_no and (d := index.by_ek.get((k.esas_no, k.karar_no))):
            add(k, d)

    forced = index.by_sira.get(forced_sira) if forced_sira is not None else None
    if forced is not None and id(forced) not in used:
        # Dosya adında sıra verilmiş: o kararın künyesine en çok benzeyen çifti bul
        for k in candidates:
            if k.karar_no and k.karar_no == forced.karar_no:
                add(k, forced, weak=True)
                break
            if k.esas_no and k.esas_no == forced.esas_no:
                add(k, forced, weak=True)
                break
        else:
            add(ParsedKunye(esas_no=None, karar_no=None, start=0), forced, weak=True)

    if not matches:
        # Tam eşleşme yoksa yalnızca karar numarasıyla (tekil ise) dene. Metindeki daire
        # kararlarına yapılan atıflar yanlış eşleşmeye yol açabileceğinden "zayıf" sayılır.
        for k in candidates:
            hits = index.by_k.get(k.karar_no or "", [])
            if len(hits) == 1:
                add(k, hits[0], weak=True)
    return matches


# --- Denetim ---------------------------------------------------------------------


def _fmt_date(d: date | None) -> str:
    return d.strftime("%d.%m.%Y") if d else "—"


def evaluate(
    m: _Match,
    rg: RgInfo,
    extracted: ExtractedText,
    profile: dict[str, Any],
) -> VerificationResult:
    d, k = m.decision, m.kunye
    checks: list[Check] = []

    def cmp(name: str, liste: Any, resmi: Any, fmt=str) -> None:
        if liste is None:
            checks.append(Check(name, None, f"{name}: listede yok, resmî metinde {fmt(resmi)}"))
        elif resmi is None:
            checks.append(Check(name, None, f"{name} resmî metinde okunamadı (listede {fmt(liste)})"))
        elif liste == resmi:
            checks.append(Check(name, True, f"{name} uyuşuyor ({fmt(resmi)})"))
        else:
            checks.append(
                Check(name, False, f"{name} farklı: listede {fmt(liste)}, resmî metinde {fmt(resmi)}",
                      hard=True)
            )

    cmp("Esas no", d.esas_no, k.esas_no)
    cmp("Karar no", d.karar_no, k.karar_no)
    cmp("Karar tarihi", d.karar_tarihi, k.karar_tarihi, _fmt_date)

    if m.weak:
        checks.append(
            Check("Eşleşme", False,
                  "Zayıf eşleşme: esas ve karar numarası birlikte bulunamadı "
                  "(yalnızca karar no veya dosya adındaki sıra ile eşleştirildi)")
        )

    if rg.tarih and rg.sayi:
        checks.append(
            Check("Resmî Gazete", True,
                  f"Resmî Gazete {_fmt_date(rg.tarih)}, sayı {rg.sayi} ({rg.kaynak})")
        )
        if d.karar_tarihi and rg.tarih < d.karar_tarihi:
            checks.append(
                Check("Resmî Gazete tarihi", False,
                      f"Resmî Gazete tarihi ({_fmt_date(rg.tarih)}) karar tarihinden önce")
            )
    else:
        checks.append(
            Check("Resmî Gazete", None,
                  "Resmî Gazete tarihi/sayısı belirlenemedi (dosya adına rg-YYYYMMDD-SAYI ekleyin)")
        )

    if mentions_all(k.segment or extracted.text, profile["keywords"]):
        checks.append(Check("Kurul", True, "Metin mahkeme/kurul adını içeriyor"))
    else:
        checks.append(Check("Kurul", False, "Metinde mahkeme veya kurul adı bulunamadı"))

    result = VerificationResult(
        file=extracted.source_name,
        sha256=extracted.sha256,
        outcome=Outcome.INCELENMELI,
        method=extracted.method,
        seed_sira=d.seed_sira,
        decision_id=d.id,
        liste_kunye={"esas_no": d.esas_no, "karar_no": d.karar_no,
                     "karar_tarihi": d.karar_tarihi.isoformat() if d.karar_tarihi else None},
        resmi_kunye={"esas_no": k.esas_no, "karar_no": k.karar_no,
                     "karar_tarihi": k.karar_tarihi.isoformat() if k.karar_tarihi else None},
        rg={"tarih": rg.tarih.isoformat() if rg.tarih else None, "sayi": rg.sayi,
            "kaynak": rg.kaynak},
        ozet=d.ozet,
    )

    if d.ozet:
        sm = compare_summary(d.ozet, k.segment or extracted.text)
        result.ozet_kapsam = sm.coverage
        result.pasaj_kapsam = sm.window_coverage
        result.pasaj = sm.passage[:1500]
        result.eksik_kelimeler = sm.missing
        pct = f"%{round(sm.coverage * 100)}"
        if sm.coverage < COVERAGE_MIN:
            checks.append(Check("Özet", False, f"Özet resmî metinle uyuşmuyor (kapsam {pct})",
                                hard=True))
        elif sm.coverage < COVERAGE_OK or sm.window_coverage < WINDOW_OK:
            checks.append(
                Check("Özet", False,
                      f"Özet kısmen uyuşuyor (kapsam {pct}, en iyi pasaj "
                      f"%{round(sm.window_coverage * 100)})")
            )
        else:
            checks.append(Check("Özet", True, f"Özet resmî metinle uyuşuyor (kapsam {pct})"))
        if sm.negation_mismatch:
            checks.append(
                Check("Hüküm yönü", False,
                      "Olumsuzluk ifadesi özet ile en yakın pasaj arasında farklı; "
                      "hükmün yönü elle kontrol edilmeli")
            )
    else:
        checks.append(Check("Özet", None, "Listede özet yok; karşılaştırılamadı"))

    result.checks = checks
    if any(c.ok is False and c.hard for c in checks):
        result.outcome = Outcome.UYUSMUYOR
    elif all(c.ok is True for c in checks):
        result.outcome = Outcome.DOGRULANDI
    else:
        result.outcome = Outcome.INCELENMELI
    return result


def verify_file(
    path: Path,
    index: DecisionIndex,
    mahkeme: str,
    cache_dir: Path | None,
) -> tuple[list[VerificationResult], dict[int, tuple[Decision, _Match]]]:
    """Bir dosyayı işler. İkinci değer: decision_id -> (karar, eşleşme) (yazma aşaması için)."""
    profile = COURT_PROFILES[mahkeme]
    try:
        extracted = extract_text(path, cache_dir)
    except ExtractionError as exc:
        from data.pipeline.text_extract import file_sha256

        return [VerificationResult(file=path.name, sha256=file_sha256(path),
                                   outcome=Outcome.METIN_YOK, hata=str(exc))], {}

    rg = parse_rg_from_filename(path.name)
    if not (rg.tarih and rg.sayi):
        rg = parse_rg_from_text(extracted.text)

    candidates = find_kunye_candidates(extracted.text)
    matches = match_candidates(candidates, index, parse_sira_from_filename(path.name))
    all_kunye = [f"E.{k.esas_no or '?'}, K.{k.karar_no or '?'}" for k in candidates]

    if not matches:
        return [VerificationResult(
            file=path.name, sha256=extracted.sha256, outcome=Outcome.ESLESMEDI,
            method=extracted.method, diger_kunyeler=all_kunye,
            hata="Metindeki künyelerin hiçbiri listedeki bir kararla eşleşmedi",
        )], {}

    assign_segments(extracted.text, [m.kunye for m in matches])
    results, writes = [], {}
    for m in matches:
        if m.decision.dogrulandi:
            results.append(VerificationResult(
                file=path.name, sha256=extracted.sha256, outcome=Outcome.KORUNDU,
                method=extracted.method, seed_sira=m.decision.seed_sira,
                decision_id=m.decision.id,
                hata=f"Zaten doğrulanmış ({m.decision.dogrulama_kaynagi}); dokunulmadı",
            ))
            continue
        r = evaluate(m, rg, extracted, profile)
        own = f"E.{m.kunye.esas_no or '?'}, K.{m.kunye.karar_no or '?'}"
        r.diger_kunyeler = [x for x in all_kunye if x != own]
        results.append(r)
        writes[m.decision.id] = (m.decision, m)
    return results, writes


def apply_result(decision: Decision, match: _Match, result: VerificationResult,
                 mahkeme: str) -> None:
    """Sonucu karara yazar. Tam metin yalnızca esas+karar birlikte eşleştiyse kaydedilir."""
    if decision.dogrulandi:
        return
    exact = not match.weak and match.kunye.esas_no == decision.esas_no \
        and match.kunye.karar_no == decision.karar_no
    if exact and match.kunye.segment:
        decision.tam_metin = match.kunye.segment
        if result.rg.get("tarih") and result.rg.get("sayi"):
            decision.resmi_gazete_tarihi = date.fromisoformat(result.rg["tarih"])
            decision.resmi_gazete_sayisi = result.rg["sayi"]
    if result.outcome is Outcome.DOGRULANDI:
        kaynak = COURT_PROFILES[mahkeme]["kaynak_adi"]
        decision.dogrulandi = True
        decision.dogrulama_kaynagi = (
            f"{kaynak} {_fmt_date(decision.resmi_gazete_tarihi)}, sayı "
            f"{decision.resmi_gazete_sayisi} (dosya: {result.file}, "
            f"sha256: {result.sha256[:12]})"
        )


# --- Durum dosyası (kaldığı yerden devam) ----------------------------------------


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(type(obj))


def load_state(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"dosyalar": {}}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=_jsonable),
                   encoding="utf-8")
    tmp.replace(path)


def result_to_dict(r: VerificationResult) -> dict[str, Any]:
    data = asdict(r)
    data["outcome"] = r.outcome.value
    return data


@dataclass
class RunSummary:
    processed: list[VerificationResult] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def run(
    session: Session,
    raw_dir: Path,
    state: dict[str, Any],
    mahkeme: str = "Danıştay",
    cache_dir: Path | None = DEFAULT_CACHE_DIR,
    force: bool = False,
) -> RunSummary:
    """raw_dir altındaki dosyaları işler, sonuçları oturuma ve state sözlüğüne yazar.
    Commit çağıranın sorumluluğundadır."""
    from data.pipeline.text_extract import file_sha256

    summary = RunSummary()
    index = DecisionIndex.load(session, mahkeme)
    files = sorted(p for p in raw_dir.rglob("*")
                   if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES)
    for path in files:
        sha = file_sha256(path)
        if not force and sha in state["dosyalar"]:
            summary.skipped.append(path.name)
            continue
        results, writes = verify_file(path, index, mahkeme, cache_dir)
        for r in results:
            if r.decision_id in writes:
                decision, match = writes[r.decision_id]
                apply_result(decision, match, r, mahkeme)
        session.flush()
        state["dosyalar"][sha] = {
            "dosya": path.name,
            "islenme_zamani": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sonuclar": [result_to_dict(r) for r in results],
        }
        summary.processed.extend(results)
    return summary


# --- Pilot listesi ve rapor -------------------------------------------------------


def pilot_records(seed: dict[str, Any], size: int = PILOT_SIZE) -> list[dict[str, Any]]:
    """İlk deneme için: künyesi tam (tarih, esas, karar) olan ilk `size` "tam" kayıt."""
    rows = [r for r in seed.get("kunyeli", [])
            if r.get("durum") == "tam" and r.get("karar_tarihi") and r.get("esas_no")
            and r.get("karar_no")]
    return rows[:size]


def _seed_date(value: str | None) -> str:
    return _fmt_date(date.fromisoformat(value)) if value else "—"


def format_download_list(seed: dict[str, Any], size: int = PILOT_SIZE) -> str:
    lines = [
        "# İndirilecek resmî metinler (ilk deneme)",
        "",
        "Bu liste `python -m data.pipeline.verify_official --liste` ile üretilir.",
        "",
        "Resmî Gazete sitesi (www.resmigazete.gov.tr) bu geliştirme ortamından erişilemediği",
        "için dosyaların elle indirilmesi gerekir. Danıştay İçtihatları Birleştirme Kurulu",
        "kararları Resmî Gazete'de yayımlanır; yayım tarihi genellikle karar tarihinden",
        "birkaç hafta ile birkaç ay sonradır. Listede Resmî Gazete tarih ve sayısı yoktur;",
        "karar tarihinden sonraki sayılar taranarak bulunmalıdır.",
        "",
        "## Nasıl kaydedilir",
        "",
        "1. Kararın yayımlandığı Resmî Gazete sayısını (PDF veya HTML) indirin.",
        "2. Dosyayı `data/raw/resmigazete/` klasörüne şu adla koyun:",
        "   `rg-YYYYMMDD-SAYI_sira-N.pdf` (ör. `rg-19700512-13500_sira-5.pdf`).",
        "   - `rg-YYYYMMDD-SAYI`: Resmî Gazete tarihi ve sayısı (doğrulama kaynağı olarak yazılır).",
        "   - `sira-N`: aşağıdaki tablodaki sıra numarası (künye OCR ile okunamazsa eşleştirmeye",
        "     yardım eder; isteğe bağlıdır).",
        "3. `python -m data.pipeline.verify_official` komutunu çalıştırın; sonuç",
        "   `docs/dogrulama_raporu.md` dosyasına yazılır.",
        "",
        "Taranmış (görüntü) PDF'ler OCR ile okunur; tarama ne kadar net olursa sonuç o kadar",
        "iyidir. Tek sayfalık görüntüler (.png, .jpg, .tif) de kabul edilir.",
        "",
        "## Liste",
        "",
        "| Sıra | Karar tarihi | Esas | Karar | Özet (ikincil kaynak) | Not |",
        "|---:|---|---|---|---|---|",
    ]
    for r in pilot_records(seed, size):
        ozet = (r.get("ozet") or "").replace("|", "\\|")
        notlar = "; ".join(r.get("notlar") or []).replace("|", "\\|")
        lines.append(
            f"| {r['sira']} | {_seed_date(r.get('karar_tarihi'))} | {r['esas_no']} | "
            f"{r['karar_no']} | {ozet} | {notlar} |"
        )
    lines.append("")
    return "\n".join(lines)


def _md(text: str | None) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def format_report(state: dict[str, Any], seed: dict[str, Any]) -> str:
    results = [r for entry in state["dosyalar"].values() for r in entry["sonuclar"]]
    by_sira: dict[int, list[dict[str, Any]]] = {}
    for r in results:
        if r.get("seed_sira") is not None:
            by_sira.setdefault(r["seed_sira"], []).append(r)

    counts: dict[str, int] = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1

    lines = [
        "# Doğrulama raporu",
        "",
        "Bu dosya `python -m data.pipeline.verify_official` tarafından her çalıştırmada",
        "baştan üretilir; elle düzenlemeyin.",
        "",
        "Doğrulama kaynağı: elle indirilen resmî metinler (`data/raw/resmigazete/`).",
        "Özet karşılaştırması sezgiseldir (kelime kökü örtüşmesi ve olumsuzluk denetimi);",
        "\"Doğrulandı\" sonuçları da hukukçu gözüyle gözden geçirilmelidir (bkz. PLAN Adım 2c).",
        "",
        "## Özet",
        "",
        f"- İşlenen dosya: {len(state['dosyalar'])}",
    ]
    for o in Outcome:
        if counts.get(o.value):
            lines.append(f"- {OUTCOME_LABELS[o]}: {counts[o.value]}")

    pilot = pilot_records(seed)
    lines += ["", "## İlk deneme listesi (10 karar)", "",
              "| Sıra | Künye (liste) | Durum | Dosya |", "|---:|---|---|---|"]
    for p in pilot:
        rs = by_sira.get(p["sira"], [])
        kunye = f"E.{p['esas_no']}, K.{p['karar_no']}, {_seed_date(p.get('karar_tarihi'))}"
        if not rs:
            lines.append(f"| {p['sira']} | {kunye} | Dosya bekleniyor | — |")
            continue
        last = rs[-1]
        lines.append(f"| {p['sira']} | {kunye} | {OUTCOME_LABELS[Outcome(last['outcome'])]} | "
                     f"{_md(last['file'])} |")

    def section(title: str, wanted: set[Outcome]) -> None:
        rows = [r for r in results if Outcome(r["outcome"]) in wanted]
        lines.extend(["", f"## {title}", ""])
        if not rows:
            lines.append("_Kayıt yok._")
            return
        for r in rows:
            head = f"### Sıra {r['seed_sira']}" if r.get("seed_sira") is not None \
                else f"### Dosya {r['file']}"
            lines.extend([head, ""])
            lines.append(f"- Sonuç: **{OUTCOME_LABELS[Outcome(r['outcome'])]}**")
            lines.append(f"- Dosya: `{r['file']}` (sha256 {r['sha256'][:12]}, yöntem: "
                         f"{r.get('method') or '—'})")
            if r.get("liste_kunye"):
                lk, rk = r["liste_kunye"], r["resmi_kunye"]
                lines.append(
                    f"- Künye (liste): E.{lk.get('esas_no') or '—'}, K.{lk.get('karar_no') or '—'}, "
                    f"{_seed_date(lk.get('karar_tarihi'))}"
                )
                lines.append(
                    f"- Künye (resmî metin): E.{rk.get('esas_no') or '—'}, "
                    f"K.{rk.get('karar_no') or '—'}, {_seed_date(rk.get('karar_tarihi'))}"
                )
            if r.get("rg", {}).get("sayi"):
                lines.append(f"- Resmî Gazete: {_seed_date(r['rg']['tarih'])}, sayı {r['rg']['sayi']}")
            for c in r.get("checks", []):
                mark = {True: "✔", False: "✘", None: "?"}[c["ok"]]
                lines.append(f"  - {mark} {c['detail']}")
            if r.get("hata"):
                lines.append(f"- Not: {r['hata']}")
            if r.get("ozet"):
                lines.append(f"- Listedeki özet: {_md(r['ozet'])}")
            if r.get("eksik_kelimeler"):
                lines.append(f"- Resmî metinde bulunmayan kelimeler: "
                             f"{', '.join(r['eksik_kelimeler'])}")
            if r.get("pasaj"):
                lines.append(f"- En yakın pasaj (resmî metin): > {_md(r['pasaj'][:800])}")
            if r.get("diger_kunyeler"):
                lines.append(f"- Metindeki diğer künyeler (atıflar olabilir): "
                             f"{'; '.join(r['diger_kunyeler'][:10])}")
            lines.append("")

    section("Uyuşmayanlar", {Outcome.UYUSMUYOR})
    section("İncelenmesi gerekenler", {Outcome.INCELENMELI})
    section("Eşleşmeyen veya okunamayan dosyalar", {Outcome.ESLESMEDI, Outcome.METIN_YOK})
    section("Doğrulananlar", {Outcome.DOGRULANDI, Outcome.KORUNDU})
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kararları resmî metinlerle doğrular.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--rapor", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED_FILE)
    parser.add_argument("--mahkeme", default="Danıştay", choices=sorted(COURT_PROFILES))
    parser.add_argument("--dry-run", action="store_true",
                        help="Veritabanına ve durum dosyasına yazmadan yalnızca raporla")
    parser.add_argument("--force", action="store_true",
                        help="Daha önce işlenen dosyaları da yeniden işle")
    parser.add_argument("--liste", action="store_true",
                        help="docs/indirilecekler.md listesini üret ve çık")
    args = parser.parse_args(argv)

    seed = json.loads(args.seed.read_text(encoding="utf-8"))
    if args.liste:
        DEFAULT_DOWNLOAD_LIST.write_text(format_download_list(seed), encoding="utf-8")
        print(f"Yazıldı: {DEFAULT_DOWNLOAD_LIST}")
        return 0

    from app.core.db import SessionLocal

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(args.state)
    with SessionLocal() as session:
        summary = run(session, args.raw_dir, state, args.mahkeme, force=args.force)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()
            save_state(args.state, state)

    report = format_report(state, seed)
    if args.dry_run:
        print("[Deneme modu: veritabanına ve durum dosyasına hiçbir şey yazılmadı]\n")
        print(report)
    else:
        args.rapor.write_text(report, encoding="utf-8")
        print(f"Rapor: {args.rapor}")

    print(f"İşlenen dosya: {len({r.file for r in summary.processed})}, "
          f"atlanan (daha önce işlenmiş): {len(summary.skipped)}")
    for o in Outcome:
        n = sum(1 for r in summary.processed if r.outcome is o)
        if n:
            print(f"  {OUTCOME_LABELS[o]}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
