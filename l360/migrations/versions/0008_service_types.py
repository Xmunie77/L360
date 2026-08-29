"""service_types: named session/additional-service price list, outside
the level+duration session-price model.

Revision ID: 0008_service_types
Revises: 0007_series_interval_weeks
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0008_service_types"
down_revision = "0007_series_interval_weeks"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.create_table(
        "service_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("client_price_cents", sa.Integer(), nullable=False),
        sa.Column("tutor_payment_cents", sa.Integer(), nullable=False),
        sa.Column("requires_room", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("name", name="uq_service_type_name"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("service_types", schema=_SCHEMA)
