"""decision_chunks.embedding için HNSW (kosinüs) indeksi

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-23
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_decision_chunks_embedding_hnsw "
        "ON decision_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_decision_chunks_embedding_hnsw")
