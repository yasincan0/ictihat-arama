"""başlangıç listesi alanları (seed_sira, seed_veri)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("decisions", sa.Column("seed_sira", sa.Integer(), nullable=True))
    op.add_column(
        "decisions",
        sa.Column("seed_veri", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_unique_constraint("uq_decisions_seed_sira", "decisions", ["seed_sira"])


def downgrade() -> None:
    op.drop_constraint("uq_decisions_seed_sira", "decisions", type_="unique")
    op.drop_column("decisions", "seed_veri")
    op.drop_column("decisions", "seed_sira")
