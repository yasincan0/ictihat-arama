import json
from datetime import date

import pytest
from sqlalchemy import func, select

from app.models import Decision, DecisionStatus
from data.pipeline.load_seed import (
    DEFAULT_SEED_FILE,
    format_report,
    load_seed,
    normalize_text,
    parse_seed,
)


@pytest.fixture
def sample():
    return {
        "mahkeme": "Danıştay",
        "kunyeli": [
            {
                "sira": 1,
                "karar_tarihi": "1966-07-09",
                "karar_yili": 1966,
                "esas_no": "1965/93",
                "karar_no": "1966/2",
                "kurul": "İçtihatları Birleştirme Kurulu",
                "ozet": "Birinci özet.",
                "durum": "tam",
                "notlar": ["Esas no başka kaynakta 1969/8"],
                "kaynak": "memurlar",
            },
            {
                # Künye eksik: esas ve karar no yok, yalnızca sıra ile eşleşebilir
                "sira": 17,
                "karar_tarihi": "1975-02-28",
                "karar_yili": 1975,
                "esas_no": None,
                "karar_no": None,
                "kurul": "İçtihatları Birleştirme Kurulu",
                "ozet": "Vekâlet ücreti.",
                "durum": "kunye_eksik",
                "notlar": [],
                "kaynak": None,
            },
        ],
        "kunyesiz": [
            {"kategori": "Vergi", "ozet": "Künyesiz özet bir.", "durum": "kunye_eksik"},
            {"kategori": "Yargılama usulü", "ozet": "Künyesiz özet iki.", "durum": "kunye_eksik"},
        ],
    }


def _count(db) -> int:
    return db.scalar(select(func.count()).select_from(Decision))


def test_parse_seed_maps_fields(sample):
    recs = parse_seed(sample)
    assert len(recs) == 4
    first = recs[0]
    assert first["karar_tarihi"] == date(1966, 7, 9)
    assert first["durum"] is DecisionStatus.TAM
    assert first["seed_sira"] == 1
    assert first["seed_veri"]["bolum"] == "kunyeli"
    kunyesiz = recs[2]
    assert kunyesiz["esas_no"] is None and kunyesiz["karar_no"] is None
    assert kunyesiz["karar_tarihi"] is None and kunyesiz["seed_sira"] is None
    assert kunyesiz["kategori"] == "Vergi"


def test_load_inserts_all_unverified(db, sample):
    report = load_seed(db, sample)
    assert len(report.added) == 4
    decisions = db.scalars(select(Decision)).all()
    assert len(decisions) == 4
    assert all(d.dogrulandi is False for d in decisions)
    kunyesiz = [d for d in decisions if d.seed_sira is None]
    assert {d.kategori for d in kunyesiz} == {"Vergi", "Yargılama usulü"}
    assert all(d.esas_no is None and d.karar_no is None for d in kunyesiz)


def test_rerun_does_not_duplicate(db, sample):
    load_seed(db, sample)
    report = load_seed(db, sample)
    assert report.added == []
    assert len(report.unchanged) == 4
    assert _count(db) == 4


def test_match_by_kunye_when_sira_missing(db, sample):
    # Sıra numarası olmadan eklenmiş bir kayıt, esas+karar no ile eşleşmeli.
    db.add(
        Decision(
            mahkeme="Danıştay",
            kurul="İçtihatları Birleştirme Kurulu",
            esas_no="1965/93",
            karar_no="1966/2",
            durum=DecisionStatus.TAM,
        )
    )
    db.flush()
    report = load_seed(db, sample)
    assert len(report.added) == 3
    assert _count(db) == 4


def test_match_by_ozet_ignores_case_and_punctuation(db, sample):
    load_seed(db, sample)
    sample["kunyesiz"][0]["ozet"] = "  KÜNYESİZ özet   bir "
    report = load_seed(db, sample)
    assert report.added == []
    assert _count(db) == 4


def test_update_changes_unverified_only(db, sample):
    load_seed(db, sample)
    first = db.scalar(select(Decision).where(Decision.seed_sira == 1))
    first.dogrulandi = True
    first.dogrulama_kaynagi = "Resmî Gazete"
    db.flush()

    sample["kunyeli"][0]["ozet"] = "Değişmiş özet."
    sample["kunyeli"][1]["ozet"] = "Değişmiş vekâlet ücreti özeti."
    report = load_seed(db, sample, update=True)

    assert [r["seed_sira"] for r in report.protected] == [1]
    assert [r["seed_sira"] for r in report.updated] == [17]
    db.refresh(first)
    assert first.ozet == "Birinci özet."  # doğrulanmış kayıt korunur
    assert db.scalar(select(Decision.ozet).where(Decision.seed_sira == 17)).startswith("Değişmiş")


def test_without_update_flag_existing_untouched(db, sample):
    load_seed(db, sample)
    sample["kunyeli"][1]["ozet"] = "Başka özet."
    load_seed(db, sample)
    assert db.scalar(select(Decision.ozet).where(Decision.seed_sira == 17)) == "Vekâlet ücreti."


def test_normalize_text_turkish():
    assert normalize_text("İSTANBUL, Işık!") == normalize_text("istanbul ışık")
    assert normalize_text(None) == ""


def test_format_report_has_totals(db, sample):
    out = format_report(load_seed(db, sample))
    assert "TOPLAM" in out and "kunye_eksik" in out and "tam" in out
    assert "dogrulandi=false" in out


def test_real_seed_file_counts(db):
    data = json.loads(DEFAULT_SEED_FILE.read_text(encoding="utf-8"))
    report = load_seed(db, data)
    bolum = [r["seed_veri"]["bolum"] for r in report.added]
    assert bolum.count("kunyeli") == 76
    assert bolum.count("kunyesiz") == 51
    assert _count(db) == 127
    assert load_seed(db, data).added == []


def test_placeholder_summary_not_stored_and_not_used_for_matching(db, sample):
    for i, sira in enumerate((30, 31)):
        sample["kunyeli"].append(
            {
                "sira": sira,
                "karar_tarihi": None,
                "karar_yili": 1980,
                "esas_no": f"1980/{i + 1}",
                "karar_no": f"1980/{i + 10}",
                "kurul": "İçtihatları Birleştirme Kurulu",
                "ozet": "Özü bulunamadı.",
                "durum": "ozet_eksik",
                "notlar": [],
                "kaynak": None,
            }
        )
    report = load_seed(db, sample)
    assert len(report.added) == 6
    d = db.scalar(select(Decision).where(Decision.seed_sira == 30))
    assert d.ozet is None
    assert d.seed_veri["ozet"] == "Özü bulunamadı."


def test_kunyesiz_not_auto_merged_with_kunyeli(db, sample):
    # Künyesiz kaydın özeti künyeli bir kararınkiyle aynı olsa bile ayrı kayıt olarak girer.
    sample["kunyesiz"].append({"kategori": "Vergi", "ozet": "Birinci özet.", "durum": "kunye_eksik"})
    report = load_seed(db, sample)
    assert len(report.added) == 5
