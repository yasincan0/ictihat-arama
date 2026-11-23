"""Arama, karar detayı ve açıklama katmanı testleri.

Embedding için HashEmbedder (ortak kelimeye dayalı test vektörü), LLM için sahte istemci
kullanılır; gerçek model/API çağrılmaz.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_db
from app.main import app
from app.models import Decision, DecisionStatus, SearchLog
from app.services.chunking import build_chunks, split_paragraphs
from app.services.embedding import HashEmbedder, get_embedder
from app.services.llm import prompts
from app.services.llm.explain import (
    Candidate,
    ExplanationError,
    explain,
    get_llm_client,
    quote_in_text,
)
from data.pipeline.embed import embed_decisions

DIM = get_settings().embedding_dim
OLAY = "Limited şirketin vergi borcu için vergi dairesi doğrudan ortağa ödeme emri gönderdi, itiraz edeceğiz."


def _d(**kw):
    base = dict(mahkeme="Danıştay", kurul="İçtihatları Birleştirme Kurulu",
                durum=DecisionStatus.TAM, notlar=[], ilgili_mevzuat=[])
    base.update(kw)
    return Decision(**base)


@pytest.fixture
def corpus(db):
    items = [
        _d(esas_no="2013/1", karar_no="2018/1", seed_sira=66, kategori="Vergi",
           ozet="Limited şirketin vergi borcunu ortaklardan tahsil etmek için önce kanuni "
                "temsilcilerin takip edilmesi gerekmez."),
        _d(esas_no="1967/10", karar_no="1970/24", seed_sira=6, kategori="Usul",
           ozet="Dava açma sürelerinin son günü tatile rastlarsa süre izleyen ilk çalışma "
                "gününün sonunda biter."),
        _d(esas_no=None, karar_no=None, kategori="Personel", durum=DecisionStatus.KUNYE_EKSIK,
           ozet="Kanuna aykırı yapılan ödemeler idarece geri alınabilir."),
        _d(esas_no="1965/93", karar_no="1966/2", seed_sira=1, ozet=None),  # metinsiz
    ]
    db.add_all(items)
    db.flush()
    stats = embed_decisions(db, HashEmbedder(DIM))
    db.commit()
    assert stats["islenen"] == 3 and stats["metinsiz"] == 1
    return items


class FakeLLM:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def complete_json(self, system, user, schema):
        self.calls.append((system, user, schema))
        if self.error:
            raise self.error
        return self.response


@pytest.fixture
def make_client(db):
    def _make(llm=None):
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_embedder] = lambda: HashEmbedder(DIM)
        app.dependency_overrides[get_llm_client] = lambda: llm
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


# --- Parçalama ve vektörleştirme -----------------------------------------------------


def test_chunking_with_and_without_full_text():
    d = _d(esas_no="1969/2", karar_no="1970/1", kategori="İmar", ozet="Kısa özet.")
    [c] = build_chunks(d)
    assert c.metin == "Kısa özet." and "E.1969/2" in c.embed_text and "İmar" in c.embed_text
    d.tam_metin = "\n\n".join(f"Paragraf {i} " + "kelime " * 60 for i in range(10))
    chunks = build_chunks(d)
    assert chunks[0].metin == "Kısa özet." and len(chunks) > 2
    assert all(len(c.metin) <= 1200 + 220 for c in chunks)
    assert split_paragraphs("a" * 3000)  # tek uzun paragraf bölünür


def test_embed_is_incremental(db, corpus):
    again = embed_decisions(db, HashEmbedder(DIM))
    assert again["islenen"] == 0
    corpus[0].ozet = corpus[0].ozet + " Değişti."
    db.flush()
    assert embed_decisions(db, HashEmbedder(DIM))["islenen"] == 1


# --- Arama ucu ------------------------------------------------------------------------


def test_search_without_llm(make_client, corpus, db):
    client = make_client(llm=None)
    r = client.post("/search", json={"olay": OLAY})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["aciklama_durumu"] == "kapali" and body["ornek_veri"] is False
    first = body["sonuclar"][0]
    assert first["karar"]["karar_no"] == "2018/1" and first["aciklama"] is None
    assert first["karar"]["dogrulandi"] is False and 0 < first["skor"] <= 1
    # Metni olmayan karar sonuçlarda yer almaz
    assert all(x["karar"]["karar_no"] != "1966/2" for x in body["sonuclar"])

    # KVKK: olay metni hiçbir yerde saklanmaz
    log = db.scalars(select(SearchLog)).one()
    assert log.query_length == len(OLAY) and log.user_id is None
    dumped = json.dumps({c.name: str(getattr(log, c.name)) for c in log.__table__.columns})
    assert "ortağa" not in dumped


def test_search_validation(make_client, corpus):
    client = make_client()
    assert client.post("/search", json={"olay": "çok kısa"}).status_code == 422
    assert client.post("/search", json={"olay": "a" * 5001}).status_code == 422


def test_search_with_llm_explanations_and_safety_nets(make_client, corpus):
    by_no = {d.karar_no: d for d in corpus}
    vergi, tatil, kunyesiz = by_no["2018/1"], by_no["1970/24"], by_no[None]
    llm = FakeLLM({
        "sonuclar": [
            # künyesiz başlıyor -> künye başa eklenmeli; alıntı metinde birebir var
            {"karar_id": vergi.id, "uygun": True,
             "aciklama": "Ortağa doğrudan gidilebileceğini söyler.",
             "alinti": "önce kanuni  temsilcilerin takip edilmesi gerekmez"},
            # uydurma alıntı -> atılmalı; uygun değil -> sona alınmalı
            {"karar_id": tatil.id, "uygun": False,
             "aciklama": "Danıştay İçtihatları Birleştirme Kurulu, E.1967/10, K.1970/24: süreyle ilgili, olayla ilgisiz.",
             "alinti": "Bu cümle karar metninde hiç geçmiyor."},
            # aday listesinde olmayan karar -> yok sayılmalı
            {"karar_id": 999999, "uygun": True, "aciklama": "uydurma", "alinti": ""},
        ],
        "genel_degerlendirme": "En uygun karar K.2018/1'dir.",
    })
    client = make_client(llm=llm)
    body = client.post("/search", json={"olay": OLAY}).json()
    assert body["aciklama_durumu"] == "tamam"
    assert body["genel_degerlendirme"] == "En uygun karar K.2018/1'dir."
    res = {r["karar"]["id"]: r for r in body["sonuclar"]}
    assert res[vergi.id]["uygun"] is True
    assert res[vergi.id]["aciklama"].startswith("Danıştay İçtihatları Birleştirme Kurulu, E.2013/1, K.2018/1")
    assert res[vergi.id]["alinti"] == "önce kanuni  temsilcilerin takip edilmesi gerekmez"
    assert res[tatil.id]["alinti"] is None and res[tatil.id]["uygun"] is False
    assert body["sonuclar"][-1]["karar"]["id"] == tatil.id
    assert 999999 not in res
    assert res[kunyesiz.id]["uygun"] is None  # değerlendirilmedi

    # İsteme olay metni, künyeler ve doğrulanmamış bilgisi gitti; künyesiz karar "bilinmiyor"
    system, user, schema = llm.calls[0]
    assert system == prompts.EXPLAIN_SYSTEM and schema == prompts.EXPLAIN_SCHEMA
    assert OLAY in user and "K.2018/1" in user and "<dogrulandi>false</dogrulandi>" in user
    assert "<kunye>bilinmiyor</kunye>" in user


def test_llm_failure_degrades_gracefully(make_client, corpus):
    client = make_client(llm=FakeLLM(error=ExplanationError("servis yok")))
    body = client.post("/search", json={"olay": OLAY}).json()
    assert body["aciklama_durumu"] == "hata"
    assert body["sonuclar"] and all(r["aciklama"] is None for r in body["sonuclar"])


def test_search_requires_login_when_configured(make_client, corpus, monkeypatch):
    monkeypatch.setenv("SEARCH_REQUIRES_LOGIN", "true")
    get_settings.cache_clear()
    try:
        client = make_client()
        assert client.post("/search", json={"olay": OLAY}).status_code == 401
        assert client.get("/config").json()["arama_giris_gerekli"] is True
    finally:
        monkeypatch.delenv("SEARCH_REQUIRES_LOGIN")
        get_settings.cache_clear()


def test_search_rate_limited(make_client, corpus):
    client = make_client()
    codes = {client.post("/search", json={"olay": OLAY}).status_code for _ in range(61)}
    assert 429 in codes


# --- Karar detayı ve yapılandırma -------------------------------------------------------


def test_decision_detail_and_config(make_client, corpus):
    client = make_client()
    d = corpus[0]
    r = client.get(f"/decisions/{d.id}").json()
    assert r["karar_no"] == "2018/1" and r["dogrulandi"] is False and r["durum"] == "tam"
    assert "tam_metin" in r and r["notlar"] == []
    assert client.get("/decisions/999999").status_code == 404
    cfg = client.get("/config").json()
    assert cfg == {**cfg, "arama_giris_gerekli": False, "abonelik_acik": False, "karar_sayisi": 3}


# --- Açıklama yardımcıları ---------------------------------------------------------------


def test_quote_in_text():
    text = "Süre, izleyen ilk çalışma\n günün sonunda biter."
    assert quote_in_text("izleyen ilk çalışma günün sonunda", text)
    assert quote_in_text("“İzleyen ilk çalışma günün sonunda biter.”", text)
    assert not quote_in_text("izleyen ikinci gün", text)
    assert not quote_in_text("biter", text)  # çok kısa alıntılar kabul edilmez


def test_explain_without_client_or_candidates():
    assert explain(OLAY, [], None).durum == "kapali"
    assert explain(OLAY, [], FakeLLM({"sonuclar": [], "genel_degerlendirme": ""})).durum == "tamam"


def test_explain_bad_items_ignored():
    c = Candidate(id=1, kunye="X, K.1970/1", konu="", dogrulandi=False, metin="metin",
                  kunye_markers=("1970/1",))
    llm = FakeLLM({"sonuclar": [{"karar_id": "abc"}, {"karar_id": 1, "uygun": True, "aciklama": ""},
                                {"karar_id": 1, "uygun": True, "aciklama": "K.1970/1 uygundur.",
                                 "alinti": ""}],
                   "genel_degerlendirme": ""})
    res = explain(OLAY, [c], llm)
    assert res.aciklamalar[1].aciklama == "K.1970/1 uygundur." and res.genel_degerlendirme is None


def test_anthropic_client_request_shape(monkeypatch):
    """Gerçek API çağrılmadan, SDK'ya giden isteğin biçimi denetlenir."""
    import anthropic

    from app.services.llm.explain import AnthropicClient

    captured = {}

    class Resp:
        stop_reason = "end_turn"
        content = [type("B", (), {"type": "text", "text": '{"sonuclar": [], "genel_degerlendirme": "yok"}'})()]

    def fake_create(**kw):
        captured.update(kw)
        return Resp()

    c = AnthropicClient("sk-test", "claude-opus-5-5", "medium", 30)
    monkeypatch.setattr(c.client.beta.messages, "create", fake_create)
    out = c.complete_json("sys", "usr", prompts.EXPLAIN_SCHEMA)
    assert out == {"sonuclar": [], "genel_degerlendirme": "yok"}
    assert captured["model"] == "claude-opus-5-5"
    assert captured["output_config"]["format"]["type"] == "json_schema"
    assert captured["output_config"]["effort"] == "medium"
    assert captured["fallbacks"] == "default" and "thinking" not in captured

    Resp.stop_reason = "refusal"
    with pytest.raises(ExplanationError):
        c.complete_json("sys", "usr", prompts.EXPLAIN_SCHEMA)
    assert anthropic  # içe aktarma kullanıldı
