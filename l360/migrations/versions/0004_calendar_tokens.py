"""calendar_tokens: per-user revocable token for the read-only iCal feed

Revision ID: 0004_calendar_tokens
Revises: 0003_billing
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0004_calendar_tokens"
down_revision = "0003_billing"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def _fk(table: str) -> str:
    return f"{L360_SCHEMA}.{table}.id" if IS_POSTGRES else f"{table}.id"


def upgrade() -> None:
    op.create_table(
        "calendar_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(_fk("users")), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token", name="uq_calendar_token"),
        sa.UniqueConstraint("user_id", name="uq_calendar_token_user"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("calendar_tokens", schema=_SCHEMA)
