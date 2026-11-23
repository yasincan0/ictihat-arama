"""Ortak test düzeni. Veritabanı testleri TEST_DATABASE_URL ile gösterilen (yoksa yereldeki
ictihat_test) PostgreSQL veritabanında çalışır; ulaşılamazsa atlanır."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://ictihat:degistir@localhost:5432/ictihat_test"
)


def _alembic_config() -> Config:
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "..", "alembic")
    )
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return cfg


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip("Test veritabanına ulaşılamadı (TEST_DATABASE_URL)")
    cfg = _alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    """Her test kendi işlemi içinde çalışır ve sonunda geri alınır."""
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """İstek sınırlayıcı süreç genelinde tek; testler birbirini etkilemesin."""
    from app.core.ratelimit import get_rate_limiter

    get_rate_limiter().reset()
    yield
    get_rate_limiter().reset()
