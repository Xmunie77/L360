"""bookings.charge_waived + outcome audit columns: educator charge
discretion on no-shows and late cancellations (Fran via Simon,
03/09/2026). True = fee waived — the booking bills nothing and pays the
tutor nothing. outcome_set_by/at record who made the money decision.

Revision ID: 0018_booking_charge_waived
Revises: 0017_booking_no_overlap
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0018_booking_charge_waived"
down_revision = "0017_booking_no_overlap"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("charge_waived", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema=_SCHEMA,
    )
    op.add_column(
        "bookings",
        sa.Column(
            "outcome_set_by_id",
            sa.Integer(),
            sa.ForeignKey(f"{L360_SCHEMA}.users.id" if IS_POSTGRES else "users.id"),
            nullable=True,
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "bookings",
        sa.Column("outcome_set_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    with op.batch_alter_table("bookings", schema=_SCHEMA) as batch_op:
        batch_op.drop_column("outcome_set_at")
        batch_op.drop_column("outcome_set_by_id")
        batch_op.drop_column("charge_waived")
