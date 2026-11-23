"""Başlangıç listesini (data/seed/danistay_ibk.json) decisions tablosuna yükler.

Kullanım (depo kökünden):
    python -m data.pipeline.load_seed [--file YOL] [--update] [--dry-run]

Kurallar (bkz. docs/PLAN.md, Adım 2a):
- Tüm kayıtlar dogrulandi=false girer; liste ikincil kaynaklardan derlenmiştir.
- "kunyesiz" kayıtlar künye alanları boş, kategori dolu olarak yüklenir.
- Tekrar çalıştırıldığında çift kayıt oluşmaz. Eşleştirme sırası:
  1) liste sıra numarası (seed_sira), 2) mahkeme + esas_no + karar_no,
  3) normalize edilmiş özet metni (yalnızca sıra numarası olmayan, yani künyesiz
     kayıtlar arasında; künyesiz bir kaydın künyeli bir kararla aynı olduğuna
     otomatik karar verilmez, bu eşleştirme Adım 2c'de onayla yapılır).
- "Özü bulunamadı." gibi yer tutucu özetler ozet alanına yazılmaz (ham hali seed_veri'de).
- Var olan kayıtlara varsayılan olarak dokunulmaz. --update verilirse yalnızca
  doğrulanmamış kayıtların listeden gelen alanları güncellenir.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from data.pipeline import _bootstrap  # noqa: F401  (app.* içe aktarımı için)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models import Decision, DecisionStatus  # noqa: E402

DEFAULT_SEED_FILE = _bootstrap.REPO_ROOT / "data" / "seed" / "danistay_ibk.json"

# Listeden gelen ve --update ile yenilenebilecek alanlar. Doğrulama sırasında
# doldurulan alanlar (tam_metin, dogrulandi, resmi gazete bilgileri vb.) burada yoktur.
SEED_FIELDS = (
    "mahkeme",
    "kurul",
    "esas_no",
    "karar_no",
    "karar_tarihi",
    "karar_yili",
    "kategori",
    "ozet",
    "kaynak",
    "durum",
    "notlar",
    "seed_sira",
    "seed_veri",
)


def normalize_text(text: str | None) -> str:
    """Özet eşleştirmesi için: küçük harf, noktalama ve fazla boşluk temizliği."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text).replace("İ", "i").replace("I", "ı").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Kaynakta özet yerine yazılmış yer tutucular (normalize edilmiş hâlleri)
PLACEHOLDER_SUMMARIES = {"özü bulunamadı"}


def _clean_summary(value: str | None) -> str | None:
    value = _clean(value)
    if value and normalize_text(value) in PLACEHOLDER_SUMMARIES:
        return None
    return value


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def parse_seed(data: dict[str, Any]) -> list[dict[str, Any]]:
    """JSON içeriğini Decision alanlarına çevrilmiş sözlükler listesine dönüştürür."""
    mahkeme = data["mahkeme"]
    records: list[dict[str, Any]] = []

    for item in data.get("kunyeli", []):
        records.append(
            {
                "mahkeme": mahkeme,
                "kurul": _clean(item.get("kurul")),
                "esas_no": _clean(item.get("esas_no")),
                "karar_no": _clean(item.get("karar_no")),
                "karar_tarihi": _parse_date(item.get("karar_tarihi")),
                "karar_yili": item.get("karar_yili"),
                "kategori": _clean(item.get("kategori")),
                "ozet": _clean_summary(item.get("ozet")),
                "kaynak": _clean(item.get("kaynak")),
                "durum": DecisionStatus(item["durum"]),
                "notlar": list(item.get("notlar") or []),
                "seed_sira": item["sira"],
                "seed_veri": {"bolum": "kunyeli", **item},
            }
        )

    for item in data.get("kunyesiz", []):
        records.append(
            {
                "mahkeme": mahkeme,
                # Kurul bilinmiyor; künye alanları bilerek boş bırakılır.
                "kurul": None,
                "esas_no": None,
                "karar_no": None,
                "karar_tarihi": None,
                "karar_yili": None,
                "kategori": _clean(item.get("kategori")),
                "ozet": _clean_summary(item.get("ozet")),
                "kaynak": _clean(item.get("kaynak")),
                "durum": DecisionStatus(item.get("durum") or DecisionStatus.KUNYE_EKSIK),
                "notlar": list(item.get("notlar") or []),
                "seed_sira": None,
                "seed_veri": {"bolum": "kunyesiz", **item},
            }
        )
    return records


@dataclass
class LoadReport:
    added: list[dict[str, Any]] = field(default_factory=list)
    updated: list[dict[str, Any]] = field(default_factory=list)
    unchanged: list[dict[str, Any]] = field(default_factory=list)
    # Eşleşen ama doğrulanmış olduğu için güncellenmeyen kayıtlar
    protected: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.added) + len(self.updated) + len(self.unchanged) + len(self.protected)


class _Index:
    """Mevcut kararları üç eşleştirme anahtarına göre bellekte tutar."""

    def __init__(self, decisions: list[Decision]):
        self.by_sira: dict[int, Decision] = {}
        self.by_kunye: dict[tuple[str, str, str], Decision] = {}
        self.by_ozet: dict[tuple[str, str], Decision] = {}
        for d in decisions:
            self.add(d)

    def add(self, d: Decision) -> None:
        if d.seed_sira is not None:
            self.by_sira[d.seed_sira] = d
        if d.esas_no and d.karar_no:
            self.by_kunye[(d.mahkeme, d.esas_no, d.karar_no)] = d
        if d.seed_sira is None and (key := normalize_text(d.ozet)):
            self.by_ozet.setdefault((d.mahkeme, key), d)

    def find(self, rec: dict[str, Any]) -> Decision | None:
        if rec["seed_sira"] is not None and rec["seed_sira"] in self.by_sira:
            return self.by_sira[rec["seed_sira"]]
        if rec["esas_no"] and rec["karar_no"]:
            hit = self.by_kunye.get((rec["mahkeme"], rec["esas_no"], rec["karar_no"]))
            if hit:
                return hit
        if rec["seed_sira"] is None and (key := normalize_text(rec["ozet"])):
            return self.by_ozet.get((rec["mahkeme"], key))
        return None


def load_seed(session: Session, data: dict[str, Any], update: bool = False) -> LoadReport:
    """Kayıtları oturuma ekler/günceller. Commit çağıranın sorumluluğundadır."""
    records = parse_seed(data)
    mahkemeler = {r["mahkeme"] for r in records}
    existing = session.scalars(select(Decision).where(Decision.mahkeme.in_(mahkemeler))).all()
    index = _Index(list(existing))
    report = LoadReport()

    for rec in records:
        found = index.find(rec)
        if found is None:
            decision = Decision(**rec, dogrulandi=False, ilgili_mevzuat=[])
            session.add(decision)
            index.add(decision)
            report.added.append(rec)
        elif not update:
            report.unchanged.append(rec)
        elif found.dogrulandi:
            report.protected.append(rec)
        else:
            changed = False
            for name in SEED_FIELDS:
                if getattr(found, name) != rec[name]:
                    setattr(found, name, rec[name])
                    changed = True
            (report.updated if changed else report.unchanged).append(rec)
            index.add(found)

    session.flush()
    return report


def format_report(report: LoadReport) -> str:
    """Durum alanına göre özet tablo üretir."""
    groups = {
        "Yeni": report.added,
        "Güncellenen": report.updated,
        "Değişmeyen": report.unchanged,
        "Korunan (doğrulanmış)": report.protected,
    }
    statuses = [s.value for s in DecisionStatus]
    all_recs = [r for recs in groups.values() for r in recs]

    def by_durum(recs: list[dict[str, Any]]) -> Counter:
        return Counter(r["durum"].value for r in recs)

    headers = ["Durum", "Künyeli", "Künyesiz", *groups.keys(), "Toplam"]
    rows = []
    for s in statuses:
        row_recs = [r for r in all_recs if r["durum"].value == s]
        if not row_recs:
            continue
        rows.append(
            [
                s,
                sum(1 for r in row_recs if r["seed_veri"]["bolum"] == "kunyeli"),
                sum(1 for r in row_recs if r["seed_veri"]["bolum"] == "kunyesiz"),
                *(by_durum(recs)[s] for recs in groups.values()),
                len(row_recs),
            ]
        )
    rows.append(
        [
            "TOPLAM",
            sum(1 for r in all_recs if r["seed_veri"]["bolum"] == "kunyeli"),
            sum(1 for r in all_recs if r["seed_veri"]["bolum"] == "kunyesiz"),
            *(len(recs) for recs in groups.values()),
            len(all_recs),
        ]
    )

    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]

    def fmt(cells: list[Any]) -> str:
        return "  ".join(
            str(c).ljust(w) if i == 0 else str(c).rjust(w)
            for i, (c, w) in enumerate(zip(cells, widths))
        )

    sep = "  ".join("-" * w for w in widths)
    lines = [fmt(headers), sep, *(fmt(r) for r in rows[:-1]), sep, fmt(rows[-1])]
    lines.append("")
    lines.append(
        "Not: Tüm kayıtlar doğrulanmamıştır (dogrulandi=false). Resmî kaynaktan "
        "doğrulanmadan kullanıcıya kesin bilgi olarak gösterilmez."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Başlangıç karar listesini veritabanına yükler.")
    parser.add_argument("--file", type=Path, default=DEFAULT_SEED_FILE, help="JSON dosyası")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Var olan doğrulanmamış kayıtları listeden gelen bilgilerle güncelle",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Değişiklikleri yazmadan yalnızca raporla"
    )
    args = parser.parse_args(argv)

    from app.core.db import SessionLocal

    data = json.loads(args.file.read_text(encoding="utf-8"))
    with SessionLocal() as session:
        report = load_seed(session, data, update=args.update)
        if args.dry_run:
            session.rollback()
            print("[Deneme modu: veritabanına hiçbir şey yazılmadı]\n")
        else:
            session.commit()
    print(f"Kaynak: {args.file}\n")
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
