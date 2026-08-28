"""notification_logs: idempotent record of every email actually sent

Revision ID: 0002_notification_logs
Revises: 0001_baseline
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0002_notification_logs"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def _fk(table: str) -> str:
    return f"{L360_SCHEMA}.{table}.id" if IS_POSTGRES else f"{table}.id"


def upgrade() -> None:
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey(_fk("bookings")), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(_fk("users")), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dedupe_key", name="uq_notification_dedupe_key"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("notification_logs", schema=_SCHEMA)
