"""Veritabanı motoru ve oturum yönetimi."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI bağımlılığı: istek başına bir oturum açar ve kapatır."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
