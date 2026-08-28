"""series_interval_weeks: weekly vs. fortnightly recurring bookings

Revision ID: 0007_series_interval_weeks
Revises: 0006_client_details
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0007_series_interval_weeks"
down_revision = "0006_client_details"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.add_column(
        "booking_series",
        sa.Column("interval_weeks", sa.Integer(), nullable=False, server_default="1"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("booking_series", "interval_weeks", schema=_SCHEMA)
