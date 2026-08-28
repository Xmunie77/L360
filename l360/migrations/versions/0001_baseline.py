"""baseline: educator levels, users, clients, rooms, price list, facility
hours/closures, booking series, bookings

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def _fk(table: str) -> str:
    return f"{L360_SCHEMA}.{table}.id" if IS_POSTGRES else f"{table}.id"


def upgrade() -> None:
    op.create_table(
        "educator_levels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema=_SCHEMA,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="educator"),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("level_id", sa.Integer(), sa.ForeignKey(_fk("educator_levels")), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index("ix_users_email", "users", ["email"], schema=_SCHEMA)

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guardian_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("child_reference", sa.String(length=200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema=_SCHEMA,
    )

    op.create_table(
        "price_list_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("level_id", sa.Integer(), sa.ForeignKey(_fk("educator_levels")), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("client_price_cents", sa.Integer(), nullable=False),
        sa.Column("educator_rate_cents", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.UniqueConstraint(
            "level_id", "duration_minutes", "valid_from",
            name="uq_price_level_duration_validfrom",
        ),
        schema=_SCHEMA,
    )

    op.create_table(
        "facility_hours",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=False),
        sa.Column("close_time", sa.Time(), nullable=False),
        sa.UniqueConstraint("weekday", name="uq_facility_hours_weekday"),
        schema=_SCHEMA,
    )

    op.create_table(
        "facility_closures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey(_fk("rooms")), nullable=True),
        schema=_SCHEMA,
    )

    op.create_table(
        "booking_series",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey(_fk("rooms")), nullable=False),
        sa.Column("educator_id", sa.Integer(), sa.ForeignKey(_fk("users")), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey(_fk("clients")), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("local_time", sa.Time(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey(_fk("rooms")), nullable=False),
        sa.Column("educator_id", sa.Integer(), sa.ForeignKey(_fk("users")), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey(_fk("clients")), nullable=False),
        sa.Column("series_id", sa.Integer(), sa.ForeignKey(_fk("booking_series")), nullable=True),
        sa.Column("start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="confirmed"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey(_fk("users")), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.create_index("ix_bookings_room_start", "bookings", ["room_id", "start_utc"], schema=_SCHEMA)
    op.create_index("ix_bookings_educator_start", "bookings", ["educator_id", "start_utc"], schema=_SCHEMA)


def downgrade() -> None:
    op.drop_table("bookings", schema=_SCHEMA)
    op.drop_table("booking_series", schema=_SCHEMA)
    op.drop_table("facility_closures", schema=_SCHEMA)
    op.drop_table("facility_hours", schema=_SCHEMA)
    op.drop_table("price_list_entries", schema=_SCHEMA)
    op.drop_table("rooms", schema=_SCHEMA)
    op.drop_table("clients", schema=_SCHEMA)
    op.drop_table("users", schema=_SCHEMA)
    op.drop_table("educator_levels", schema=_SCHEMA)
