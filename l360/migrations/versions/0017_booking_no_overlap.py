"""Database-level double-booking prevention (P1-2 of the 31/08/2026 review).

Two GiST exclusion constraints on bookings: no two ACTIVE (confirmed/
completed) bookings may overlap in time for the same room, nor for the same
educator. The app-level validate_slot() check remains the friendly first
line (clear error messages, works on SQLite in dev); these constraints close
the race where two simultaneous requests both pass that check — Postgres
itself refuses the second insert, and the API maps that to the same 409.

Postgres-only: SQLite has no exclusion constraints, and dev/tests don't
have concurrent writers.

Revision ID: 0017_booking_no_overlap
Revises: 0016_login_lockout
Create Date: 2026-08-31
"""
from alembic import op

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0017_booking_no_overlap"
down_revision = "0016_login_lockout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not IS_POSTGRES:
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(f"""
        ALTER TABLE {L360_SCHEMA}.bookings ADD CONSTRAINT excl_booking_room_overlap
        EXCLUDE USING gist (
            room_id WITH =,
            tstzrange(start_utc, start_utc + make_interval(mins => duration_minutes)) WITH &&
        ) WHERE (status IN ('confirmed', 'completed'))
    """)
    op.execute(f"""
        ALTER TABLE {L360_SCHEMA}.bookings ADD CONSTRAINT excl_booking_educator_overlap
        EXCLUDE USING gist (
            educator_id WITH =,
            tstzrange(start_utc, start_utc + make_interval(mins => duration_minutes)) WITH &&
        ) WHERE (status IN ('confirmed', 'completed'))
    """)


def downgrade() -> None:
    if not IS_POSTGRES:
        return
    op.execute(f"ALTER TABLE {L360_SCHEMA}.bookings DROP CONSTRAINT IF EXISTS excl_booking_room_overlap")
    op.execute(f"ALTER TABLE {L360_SCHEMA}.bookings DROP CONSTRAINT IF EXISTS excl_booking_educator_overlap")
