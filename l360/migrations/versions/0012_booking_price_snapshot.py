"""booking_price_snapshot: bookings get client_price_cents and
tutor_payment_cents, copied from the service type at booking time (and
re-copied on a move that changes the service type). The L360 price list
(service_types) is a flat, admin-editable table with no per-entry history
— without this snapshot, editing a price would retroactively change what
any not-yet-billed past session invoices at. Billing/statements price
from these columns from here on, not a live ServiceType lookup.

Revision ID: 0012_booking_price_snapshot
Revises: 0011_booking_service_type
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0012_booking_price_snapshot"
down_revision = "0011_booking_service_type"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("client_price_cents", sa.Integer(), nullable=True), schema=_SCHEMA)
    op.add_column("bookings", sa.Column("tutor_payment_cents", sa.Integer(), nullable=True), schema=_SCHEMA)


def downgrade() -> None:
    op.drop_column("bookings", "tutor_payment_cents", schema=_SCHEMA)
    op.drop_column("bookings", "client_price_cents", schema=_SCHEMA)
