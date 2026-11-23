"""ödeme: ödeme formu oturumları ve sağlayıcı müşteri kodu

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("provider_customer_id", sa.String(200), nullable=True))
    op.create_table(
        "payment_checkouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("token", sa.String(200), nullable=False, unique=True),
        sa.Column("plan", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.String(50), nullable=True),
    )
    op.create_index("ix_payment_checkouts_user_id", "payment_checkouts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_checkouts_user_id", table_name="payment_checkouts")
    op.drop_table("payment_checkouts")
    op.drop_column("subscriptions", "provider_customer_id")
