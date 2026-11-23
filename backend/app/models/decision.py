"""Karar ve karar parçası (chunk) modelleri. Mahkemeden bağımsız tasarlanmıştır."""

import enum
from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.models.base import Base, TimestampMixin


class DecisionStatus(str, enum.Enum):
    """Başlangıç listesindeki `durum` alanının değerleri (bkz. CLAUDE.md)."""

    TAM = "tam"
    OZET_EKSIK = "ozet_eksik"
    ESLESTIRME_BELIRSIZ = "eslestirme_belirsiz"
    NUMARA_SUPHELI = "numara_supheli"
    HUKUM_YONU_EKSIK = "hukum_yonu_eksik"
    KUNYE_EKSIK = "kunye_eksik"


class Decision(TimestampMixin, Base):
    __tablename__ = "decisions"
    __table_args__ = (
        UniqueConstraint("mahkeme", "kurul", "esas_no", "karar_no", name="uq_decision_kunye"),
        Index("ix_decisions_durum", "durum"),
        Index("ix_decisions_dogrulandi", "dogrulandi"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mahkeme: Mapped[str] = mapped_column(String(100), nullable=False)
    kurul: Mapped[str | None] = mapped_column(String(200))  # daire veya kurul
    esas_no: Mapped[str | None] = mapped_column(String(50))
    karar_no: Mapped[str | None] = mapped_column(String(50))
    karar_tarihi: Mapped[date | None] = mapped_column(Date)
    karar_yili: Mapped[int | None] = mapped_column(Integer)
    resmi_gazete_tarihi: Mapped[date | None] = mapped_column(Date)
    resmi_gazete_sayisi: Mapped[str | None] = mapped_column(String(20))
    kategori: Mapped[str | None] = mapped_column(String(200))
    konu: Mapped[str | None] = mapped_column(Text)
    ozet: Mapped[str | None] = mapped_column(Text)
    tam_metin: Mapped[str | None] = mapped_column(Text)
    ilgili_mevzuat: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    kaynak_url: Mapped[str | None] = mapped_column(String(1000))
    kaynak: Mapped[str | None] = mapped_column(String(100))  # özetin alındığı ikincil kaynak
    durum: Mapped[DecisionStatus] = mapped_column(
        Enum(
            DecisionStatus,
            name="decision_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    notlar: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    dogrulandi: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dogrulama_kaynagi: Mapped[str | None] = mapped_column(String(1000))

    chunks: Mapped[list["DecisionChunk"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan", order_by="DecisionChunk.sira"
    )

    @property
    def kunye(self) -> str:
        """Kullanıcıya gösterilecek kısa künye, ör. 'Danıştay İBK, E.1965/93, K.1966/2'."""
        parts = [self.mahkeme]
        if self.kurul:
            parts[0] += f" {self.kurul}"
        if self.esas_no:
            parts.append(f"E.{self.esas_no}")
        if self.karar_no:
            parts.append(f"K.{self.karar_no}")
        if self.karar_tarihi:
            parts.append(self.karar_tarihi.strftime("%d.%m.%Y"))
        return ", ".join(parts)


class DecisionChunk(Base):
    __tablename__ = "decision_chunks"
    __table_args__ = (UniqueConstraint("decision_id", "sira", name="uq_chunk_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sira: Mapped[int] = mapped_column(Integer, nullable=False)
    metin: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(get_settings().embedding_dim))

    decision: Mapped[Decision] = relationship(back_populates="chunks")
