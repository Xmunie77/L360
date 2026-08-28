"""password_reset_tokens: single-use, time-limited forgot-password tokens

Revision ID: 0005_password_reset_tokens
Revises: 0004_calendar_tokens
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0005_password_reset_tokens"
down_revision = "0004_calendar_tokens"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def _fk(table: str) -> str:
    return f"{L360_SCHEMA}.{table}.id" if IS_POSTGRES else f"{table}.id"


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(_fk("users")), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token", name="uq_password_reset_token"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("password_reset_tokens", schema=_SCHEMA)
