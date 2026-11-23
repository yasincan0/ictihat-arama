"""Resmî metinle doğrulama hattının testleri.

Buradaki metinler test için yazılmış ÖRNEK metinlerdir; gerçek karar metni değildir.
"""

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from app.models import Decision
from data.pipeline.kunye import (
    assign_segments,
    compare_summary,
    find_karar_tarihi,
    find_kunye_candidates,
    has_negation,
    parse_rg_from_filename,
    parse_rg_from_text,
    parse_sira_from_filename,
)
from data.pipeline.load_seed import DEFAULT_SEED_FILE, load_seed
from data.pipeline.text_extract import extract_text, html_to_text, decode_bytes
from data.pipeline.verify_official import (
    Outcome,
    format_download_list,
    format_report,
    pilot_records,
    run,
)

OZET = (
    "Parselasyon planlarına karşı açılan davalarda dava açma süresi, Anayasa'nın 114. "
    "maddesine göre yazılı bildirim tarihinden itibaren başlar."
)

ORNEK_METIN = """RESMÎ GAZETE
12 Mayıs 1970 SALI Sayı: 13500
YARGI BÖLÜMÜ
Danıştay İçtihatları Birleştirme Kurulu Kararı
Esas No : 1969/2
Karar No : 1970/1
Karar Tarihi : 12.2.1970
(Bu metin test için yazılmış örnek metindir.)
Danıştay Beşinci Dairesinin E.1965/100, K.1966/200 sayılı kararı ile Sekizinci Dairesinin
kararı arasında aykırılık bulunduğu ileri sürülmüştür. Konu görüşüldü.
Sonuç olarak, parselasyon planlarına karşı açılacak davalarda dava açma süresinin,
Anayasa'nın 114. maddesi uyarınca planın yazılı bildirim tarihinden itibaren başlayacağına
12.2.1970 tarihinde oyçokluğuyla karar verildi.
"""


@pytest.fixture
def seed_sample():
    def rec(sira, tarih, esas, karar, ozet, notlar=()):
        return {
            "sira": sira, "karar_tarihi": tarih, "karar_yili": int(tarih[:4]),
            "esas_no": esas, "karar_no": karar, "kurul": "İçtihatları Birleştirme Kurulu",
            "ozet": ozet, "durum": "tam", "notlar": list(notlar), "kaynak": "danistay",
        }

    return {
        "mahkeme": "Danıştay",
        "kunyeli": [
            rec(5, "1970-02-12", "1969/2", "1970/1", OZET),
            rec(15, "1973-12-22", "1968/8", "1973/14",
                "Kanuna aykırı terfi sonucu fazla ödenen aylıklar 90 gün içinde geri alınabilir.",
                ["Esas no başka kaynakta 1969/8"]),
            rec(21, "1979-03-08", "1971/1", "1979/1",
                "TMMOB'un dava açma ve davada taraf olma ehliyeti vardır."),
        ],
        "kunyesiz": [],
    }


@pytest.fixture
def dirs(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    return raw, tmp_path / "cache"


# --- Künye ayrıştırma ----------------------------------------------------------


def test_find_kunye_candidates_includes_references():
    cands = find_kunye_candidates(ORNEK_METIN)
    pairs = [(c.esas_no, c.karar_no) for c in cands]
    assert pairs == [("1969/2", "1970/1"), ("1965/100", "1966/200")]


def test_kunye_variants():
    text = "E.1971/9, K.1979/5 ... Esas Numarası: 1976/01 Karar Numarası: 1979/010"
    pairs = [(c.esas_no, c.karar_no) for c in find_kunye_candidates(text)]
    assert pairs == [("1971/9", "1979/5"), ("1976/1", "1979/10")]


def test_karar_tarihi_label_and_fallback():
    assert find_karar_tarihi("Karar Tarihi : 12.2.1970") == date(1970, 2, 12)
    assert find_karar_tarihi("Karar Günü: 9 Mayıs 1970") == date(1970, 5, 9)
    text = "... gerekçesiyle 20.6.1970 tarihinde oybirliğiyle karar verildi."
    assert find_karar_tarihi(text) == date(1970, 6, 20)
    assert find_karar_tarihi("tarih yok") is None


def test_assign_segments_splits_between_decisions():
    text = "Esas No: 1969/2 Karar No: 1970/1 birinci metin. " + "x " * 400 + \
           "Esas No: 1971/1 Karar No: 1979/1 Karar Tarihi: 8.3.1979 ikinci metin."
    cands = [c for c in find_kunye_candidates(text)]
    segs = assign_segments(text, cands)
    assert "birinci" in segs[0].segment and "ikinci" not in segs[0].segment
    assert "ikinci" in segs[1].segment and segs[1].karar_tarihi == date(1979, 3, 8)


def test_rg_info():
    rg = parse_rg_from_filename("rg-19700512-13500_sira-5.pdf")
    assert (rg.tarih, rg.sayi, rg.kaynak) == (date(1970, 5, 12), "13500", "dosya_adi")
    assert parse_rg_from_filename("karar.pdf").tarih is None
    assert parse_sira_from_filename("rg-19700512-13500_sira-5.pdf") == 5
    rg = parse_rg_from_text(ORNEK_METIN)
    assert (rg.tarih, rg.sayi, rg.kaynak) == (date(1970, 5, 12), "13500", "metin")
    assert parse_rg_from_text("Esas No: 1969/2").sayi is None


# --- Özet karşılaştırma ---------------------------------------------------------


def test_compare_summary_matching_and_unrelated():
    good = compare_summary(OZET, ORNEK_METIN)
    assert good.coverage >= 0.9 and good.window_coverage >= 0.7
    assert "parselasyon" in good.passage.lower()
    assert not good.negation_mismatch

    bad = compare_summary("Otomatik oyun makineleri kumar aletidir.", ORNEK_METIN)
    assert bad.coverage < 0.5
    assert "kumar" in bad.missing


def test_negation_detection():
    assert has_negation("süre aranmaz") and has_negation("görevine son verilemez")
    assert has_negation("yargısal nitelik taşımaz") and has_negation("ehliyeti yoktur")
    assert not has_negation("süre izleyen iş gününde biter")
    sm = compare_summary(OZET.replace("başlar", "başlamaz"), ORNEK_METIN)
    assert sm.negation_mismatch


# --- Metin çıkarma ---------------------------------------------------------------


def test_html_cp1254(tmp_path):
    html = "<html><head><title>x</title></head><body><p>Danıştay İçtihatları</p>" \
           "<p>Esas No: 1969/2</p></body></html>"
    f = tmp_path / "rg.htm"
    f.write_bytes(html.encode("cp1254"))
    assert decode_bytes(f.read_bytes()).count("ş") == 1
    text = extract_text(f, None).text
    assert "Danıştay İçtihatları" in text and "1969/2" in text and "x" not in text.split()
    assert html_to_text("<p>a</p><p>b</p>").split() == ["a", "b"]


def _minimal_text_pdf(path: Path, lines: list[str]) -> None:
    """Metin katmanlı, yalnızca ASCII içeren basit bir PDF yazar."""
    content = "BT /F1 11 Tf 40 800 Td 14 TL " + " ".join(
        "(" + ln.replace("(", "").replace(")", "") + ") '" for ln in lines
    ) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    path.write_bytes(out.encode("latin-1"))


def test_pdf_text_layer_and_cache(tmp_path):
    f = tmp_path / "metin.pdf"
    lines = ["Danistay Ictihatlari Birlestirme Kurulu", "Esas No: 1969/2", "Karar No: 1970/1"]
    lines += ["Bu satir test icin yazilmis ornek bir metindir ve yeterince harf icerir."] * 5
    _minimal_text_pdf(f, lines)
    cache = tmp_path / "cache"
    res = extract_text(f, cache)
    assert res.method == "pdf" and "1969/2" in res.text
    assert len(list(cache.glob("*.json"))) == 1
    # İkinci çağrı önbellekten gelir (dosya yeniden okunmaz)
    (cache / f"{res.sha256}.json").write_text(
        json.dumps({**res.__dict__, "text": "ONBELLEK"}), encoding="utf-8"
    )
    assert extract_text(f, cache).text == "ONBELLEK"


def _font():
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        if Path(p).exists():
            return p
    return None


@pytest.mark.skipif(not (shutil.which("tesseract") and shutil.which("pdftoppm") and _font()),
                    reason="OCR araçları (tesseract, pdftoppm) veya yazı tipi yok")
def test_scanned_pdf_is_ocr_ed(tmp_path):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (2000, 700), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_font(), 48)
    for i, ln in enumerate(["Danıştay İçtihatları Birleştirme Kurulu",
                            "Esas No: 1969/2", "Karar No: 1970/1"]):
        draw.text((60, 60 + i * 120), ln, fill="black", font=font)
    f = tmp_path / "tarama.pdf"
    img.save(f, "PDF", resolution=200)
    res = extract_text(f, None)
    assert res.method == "ocr"
    cands = find_kunye_candidates(res.text)
    assert ("1969/2", "1970/1") in [(c.esas_no, c.karar_no) for c in cands]
    assert "Danıştay" in res.text


# --- Uçtan uca (veritabanı) -------------------------------------------------------


def _decision(db, sira):
    from sqlalchemy import select

    return db.scalars(select(Decision).where(Decision.seed_sira == sira)).one()


def test_run_verifies_matching_and_reports_mismatch(db, seed_sample, dirs):
    raw, cache = dirs
    load_seed(db, seed_sample)
    (raw / "rg-19700512-13500_sira-5.txt").write_text(ORNEK_METIN, encoding="utf-8")
    # Sıra 15: esas no listedekinden farklı (1969/8), karar no aynı
    (raw / "rg-19740301-14800.txt").write_text(
        "Danıştay İçtihatları Birleştirme Kurulu\nEsas No: 1969/8\nKarar No: 1973/14\n"
        "Karar Tarihi: 22.12.1973\nKanuna aykırı terfi sonucu fazla ödenen aylıklar 90 gün "
        "içinde geri alınabilir.\n", encoding="utf-8")
    # Sıra 21: künye doğru ama metin başka konuda
    (raw / "rg-19790601-16600.txt").write_text(
        "Danıştay İçtihatları Birleştirme Kurulu\nEsas No: 1971/1\nKarar No: 1979/1\n"
        "Karar Tarihi: 8.3.1979\nOtomatik oyun makineleri kumar aleti sayılır.\n",
        encoding="utf-8")
    # Listede olmayan bir karar
    (raw / "baska.txt").write_text("Esas No: 1990/1 Karar No: 1991/1", encoding="utf-8")

    state = {"dosyalar": {}}
    summary = run(db, raw, state, cache_dir=cache)
    outcomes = {r.file: r.outcome for r in summary.processed}
    assert outcomes == {
        "rg-19700512-13500_sira-5.txt": Outcome.DOGRULANDI,
        "rg-19740301-14800.txt": Outcome.UYUSMUYOR,
        "rg-19790601-16600.txt": Outcome.UYUSMUYOR,
        "baska.txt": Outcome.ESLESMEDI,
    }

    d5 = _decision(db, 5)
    assert d5.dogrulandi is True
    assert d5.resmi_gazete_tarihi == date(1970, 5, 12) and d5.resmi_gazete_sayisi == "13500"
    assert d5.dogrulama_kaynagi.startswith("Resmî Gazete 12.05.1970, sayı 13500")
    assert "parselasyon" in d5.tam_metin.lower()

    d15 = _decision(db, 15)
    assert d15.dogrulandi is False
    assert d15.tam_metin is None  # zayıf eşleşmede tam metin yazılmaz
    r15 = next(r for r in summary.processed if r.seed_sira == 15)
    assert any("Esas no farklı" in x for x in r15.reasons)

    d21 = _decision(db, 21)
    assert d21.dogrulandi is False
    assert d21.tam_metin is not None  # künye birebir eşleşti; metin saklanır
    r21 = next(r for r in summary.processed if r.seed_sira == 21)
    assert any("uyuşmuyor" in x for x in r21.reasons)

    report = format_report(json.loads(json.dumps(state, default=str)), seed_sample)
    assert "## Uyuşmayanlar" in report and "Esas no farklı" in report
    assert "### Sıra 5" in report and "Doğrulandı" in report

    # Kaldığı yerden devam: ikinci çalıştırmada hiçbir dosya yeniden işlenmez
    again = run(db, raw, state, cache_dir=cache)
    assert again.processed == [] and len(again.skipped) == 4

    # --force ile yeniden işlenirse doğrulanmış kayıt korunur
    forced = run(db, raw, state, cache_dir=cache, force=True)
    assert next(r for r in forced.processed if r.seed_sira == 5).outcome is Outcome.KORUNDU


def test_run_needs_rg_info_and_flags_negation(db, seed_sample, dirs):
    raw, cache = dirs
    load_seed(db, seed_sample)
    # RG tarih/sayısı yok (dosya adında ve metinde) -> incelenmeli
    (raw / "karar.txt").write_text(ORNEK_METIN.split("YARGI BÖLÜMÜ", 1)[1], encoding="utf-8")
    summary = run(db, raw, {"dosyalar": {}}, cache_dir=cache)
    [r] = summary.processed
    assert r.outcome is Outcome.INCELENMELI
    assert any("Resmî Gazete tarihi/sayısı belirlenemedi" in x for x in r.reasons)
    assert _decision(db, 5).dogrulandi is False

    # Hüküm yönü ters -> incelenmeli
    db.rollback()
    neg = ORNEK_METIN.replace("başlayacağına", "başlamayacağına")
    raw2 = raw.parent / "raw2"
    raw2.mkdir()
    (raw2 / "rg-19700512-13500.txt").write_text(neg, encoding="utf-8")
    load_seed(db, seed_sample)
    [r] = run(db, raw2, {"dosyalar": {}}, cache_dir=cache).processed
    assert r.outcome is Outcome.INCELENMELI
    assert any("hükmün yönü" in x for x in r.reasons)


def test_unsupported_and_unreadable_files_are_reported(db, seed_sample, dirs):
    raw, cache = dirs
    load_seed(db, seed_sample)
    (raw / "notlar.docx").write_bytes(b"x")  # desteklenmeyen tür: hiç işlenmez
    (raw / "bozuk.pdf").write_bytes(b"%PDF-1.4 bozuk")
    summary = run(db, raw, {"dosyalar": {}}, cache_dir=cache)
    assert [(r.file, r.outcome) for r in summary.processed] == [("bozuk.pdf", Outcome.METIN_YOK)]


def test_pilot_and_download_list_from_real_seed():
    seed = json.loads(Path(DEFAULT_SEED_FILE).read_text(encoding="utf-8"))
    pilot = pilot_records(seed)
    assert len(pilot) == 10
    assert all(p["durum"] == "tam" and p["esas_no"] and p["karar_no"] and p["karar_tarihi"]
               for p in pilot)
    md = format_download_list(seed)
    assert md.count("\n| ") == 10 + 1  # başlık satırı + 10 karar
    report = format_report({"dosyalar": {}}, seed)
    assert report.count("Dosya bekleniyor") == 10
