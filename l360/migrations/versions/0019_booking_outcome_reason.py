"""bookings.outcome_reason: why a fee was waived (Child ill / Educator
ill / Family emergency / Other — Simon, 03/09/2026). Recorded by the
Confirm flow's reason step; cleared if an admin re-charges.

Revision ID: 0019_booking_outcome_reason
Revises: 0018_booking_charge_waived
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0019_booking_outcome_reason"
down_revision = "0018_booking_charge_waived"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("outcome_reason", sa.String(100), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    with op.batch_alter_table("bookings", schema=_SCHEMA) as batch_op:
        batch_op.drop_column("outcome_reason")
