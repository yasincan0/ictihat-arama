from datetime import date

import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models import Decision, DecisionChunk, DecisionStatus, SearchLog, User
from tests.conftest import _alembic_config


def _decision(**kw) -> Decision:
    data = dict(
        mahkeme="Danıştay",
        kurul="İçtihatları Birleştirme Kurulu",
        esas_no="1965/93",
        karar_no="1966/2",
        durum=DecisionStatus.TAM,
    )
    data.update(kw)
    return Decision(**data)


def test_pgvector_extension_enabled(db):
    assert db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar() == 1


def test_embedding_dimension_comes_from_settings(engine):
    cols = {c["name"]: c for c in inspect(engine).get_columns("decision_chunks")}
    assert cols["embedding"]["type"].dim == get_settings().embedding_dim


def test_decision_defaults_unverified(db):
    d = _decision()
    db.add(d)
    db.flush()
    db.refresh(d)
    assert d.dogrulandi is False
    assert d.notlar == [] and d.ilgili_mevzuat == []
    assert d.created_at is not None


def test_kunye_format():
    d = _decision(karar_tarihi=date(1966, 3, 14))
    assert d.kunye == "Danıştay İçtihatları Birleştirme Kurulu, E.1965/93, K.1966/2, 14.03.1966"


def test_duplicate_kunye_rejected(db):
    db.add(_decision())
    db.flush()
    db.add(_decision())
    with pytest.raises(IntegrityError):
        db.flush()


def test_kunyesiz_records_do_not_collide(db):
    # Künyesiz kararlarda esas/karar no NULL'dır; birden fazla kayıt girilebilmeli.
    for ozet in ("a", "b"):
        db.add(_decision(esas_no=None, karar_no=None, ozet=ozet, durum=DecisionStatus.KUNYE_EKSIK))
    db.flush()


def test_chunk_embedding_and_similarity_search(db):
    dim = get_settings().embedding_dim
    d = _decision()
    d.chunks = [
        DecisionChunk(sira=0, metin="birinci", embedding=[1.0] + [0.0] * (dim - 1)),
        DecisionChunk(sira=1, metin="ikinci", embedding=[0.0, 1.0] + [0.0] * (dim - 2)),
    ]
    db.add(d)
    db.flush()
    query = [0.9, 0.1] + [0.0] * (dim - 2)
    nearest = db.scalars(
        select(DecisionChunk).order_by(DecisionChunk.embedding.cosine_distance(query)).limit(1)
    ).one()
    assert nearest.metin == "birinci"


def test_deleting_decision_deletes_chunks(db):
    d = _decision()
    d.chunks = [DecisionChunk(sira=0, metin="x")]
    db.add(d)
    db.flush()
    db.delete(d)
    db.flush()
    assert db.scalars(select(DecisionChunk)).all() == []


def test_search_log_has_no_query_text_column():
    # KVKK: olay özeti arama günlüğünde saklanmaz.
    columns = set(SearchLog.__table__.columns.keys())
    assert not columns & {"query", "query_text", "olay", "olay_ozeti", "metin"}


def test_user_email_unique(db):
    db.add(User(email="a@ornek.com", password_hash="x"))
    db.flush()
    db.add(User(email="a@ornek.com", password_hash="y"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_migration_downgrade_and_upgrade(engine):
    cfg = _alembic_config()
    command.downgrade(cfg, "base")
    assert "decisions" not in inspect(engine).get_table_names()
    command.upgrade(cfg, "head")
    assert {"decisions", "decision_chunks", "users", "subscriptions", "search_logs"} <= set(
        inspect(engine).get_table_names()
    )
