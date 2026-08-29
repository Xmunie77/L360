"""booking_service_type: bookings and booking_series each get a
service_type_id, so a session is priced by picking a named item from the
L360 price list (service_types) instead of educator level + duration.
Nullable — existing rows have none, and older code paths that don't know
about it keep working; billing/statements treat a null service_type_id as
unpriced going forward.

Revision ID: 0010_booking_service_type
Revises: 0009_onboarding
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0010_booking_service_type"
down_revision = "0009_onboarding"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    # batch mode: SQLite can't ALTER a table to add a column with a foreign
    # key constraint in place — batch mode does the copy-and-move dance for
    # us, and is a no-op wrapper on Postgres.
    with op.batch_alter_table("booking_series", schema=_SCHEMA) as batch_op:
        batch_op.add_column(sa.Column("service_type_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_booking_series_service_type_id", "service_types", ["service_type_id"], ["id"],
            referent_schema=_SCHEMA,
        )
    with op.batch_alter_table("bookings", schema=_SCHEMA) as batch_op:
        batch_op.add_column(sa.Column("service_type_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_bookings_service_type_id", "service_types", ["service_type_id"], ["id"],
            referent_schema=_SCHEMA,
        )


def downgrade() -> None:
    with op.batch_alter_table("bookings", schema=_SCHEMA) as batch_op:
        batch_op.drop_constraint("fk_bookings_service_type_id", type_="foreignkey")
        batch_op.drop_column("service_type_id")
    with op.batch_alter_table("booking_series", schema=_SCHEMA) as batch_op:
        batch_op.drop_constraint("fk_booking_series_service_type_id", type_="foreignkey")
        batch_op.drop_column("service_type_id")
