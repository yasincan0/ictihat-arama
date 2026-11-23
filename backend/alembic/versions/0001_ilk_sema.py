"""ilk sema

Revision ID: 0001
Revises: 
Create Date: 2026-11-23 01:40:56.484122
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector eklentisi; embedding boyutu ayardan (EMBEDDING_DIM) okunur.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('decisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('mahkeme', sa.String(length=100), nullable=False),
    sa.Column('kurul', sa.String(length=200), nullable=True),
    sa.Column('esas_no', sa.String(length=50), nullable=True),
    sa.Column('karar_no', sa.String(length=50), nullable=True),
    sa.Column('karar_tarihi', sa.Date(), nullable=True),
    sa.Column('karar_yili', sa.Integer(), nullable=True),
    sa.Column('resmi_gazete_tarihi', sa.Date(), nullable=True),
    sa.Column('resmi_gazete_sayisi', sa.String(length=20), nullable=True),
    sa.Column('kategori', sa.String(length=200), nullable=True),
    sa.Column('konu', sa.Text(), nullable=True),
    sa.Column('ozet', sa.Text(), nullable=True),
    sa.Column('tam_metin', sa.Text(), nullable=True),
    sa.Column('ilgili_mevzuat', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('kaynak_url', sa.String(length=1000), nullable=True),
    sa.Column('kaynak', sa.String(length=100), nullable=True),
    sa.Column('durum', sa.Enum('tam', 'ozet_eksik', 'eslestirme_belirsiz', 'numara_supheli', 'hukum_yonu_eksik', 'kunye_eksik', name='decision_status'), nullable=False),
    sa.Column('notlar', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('dogrulandi', sa.Boolean(), nullable=False),
    sa.Column('dogrulama_kaynagi', sa.String(length=1000), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('mahkeme', 'kurul', 'esas_no', 'karar_no', name='uq_decision_kunye')
    )
    op.create_index('ix_decisions_dogrulandi', 'decisions', ['dogrulandi'], unique=False)
    op.create_index('ix_decisions_durum', 'decisions', ['durum'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=True),
    sa.Column('baro_sicil_no', sa.String(length=50), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('email_verified', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('decision_chunks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('decision_id', sa.Integer(), nullable=False),
    sa.Column('sira', sa.Integer(), nullable=False),
    sa.Column('metin', sa.Text(), nullable=False),
    sa.Column('embedding', Vector(get_settings().embedding_dim), nullable=True),
    sa.ForeignKeyConstraint(['decision_id'], ['decisions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('decision_id', 'sira', name='uq_chunk_order')
    )
    op.create_index(op.f('ix_decision_chunks_decision_id'), 'decision_chunks', ['decision_id'], unique=False)
    op.create_table('search_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('query_length', sa.Integer(), nullable=False),
    sa.Column('result_count', sa.Integer(), nullable=False),
    sa.Column('result_decision_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_search_logs_created_at'), 'search_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_search_logs_user_id'), 'search_logs', ['user_id'], unique=False)
    op.create_table('subscriptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('plan', sa.String(length=50), nullable=False),
    sa.Column('status', sa.Enum('active', 'past_due', 'canceled', 'expired', name='subscription_status'), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('provider_subscription_id', sa.String(length=200), nullable=True),
    sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider_subscription_id')
    )
    op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_subscriptions_user_id'), table_name='subscriptions')
    op.drop_table('subscriptions')
    op.drop_index(op.f('ix_search_logs_user_id'), table_name='search_logs')
    op.drop_index(op.f('ix_search_logs_created_at'), table_name='search_logs')
    op.drop_table('search_logs')
    op.drop_index(op.f('ix_decision_chunks_decision_id'), table_name='decision_chunks')
    op.drop_table('decision_chunks')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index('ix_decisions_durum', table_name='decisions')
    op.drop_index('ix_decisions_dogrulandi', table_name='decisions')
    op.drop_table('decisions')
    sa.Enum(name='subscription_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='decision_status').drop(op.get_bind(), checkfirst=True)
