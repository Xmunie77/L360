"""SQLAlchemy models for Learning 360° (l360).

SQLAlchemy 2.0 Mapped/mapped_column style, mirroring kitchentable/models.py:
tables are scoped to the app's own Postgres schema in production and unscoped
on SQLite (dev/tests). Money is stored as integer cents everywhere; datetimes
are stored as timezone-aware UTC.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from l360.config import IS_POSTGRES, L360_SCHEMA


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Timezone-aware DateTime that round-trips correctly on SQLite too.

    Postgres' TIMESTAMPTZ round-trips tz-aware values natively, but SQLite
    has no native timestamp type — SQLAlchemy silently stores/returns naive
    datetimes there even when the column is declared timezone=True. That
    turns any `booking.start_utc > datetime.now(UTC)` comparison into a
    TypeError in tests (and would be a silent UTC/local mixup in prod if
    ever pointed at SQLite). This type always stores naive-but-known-UTC on
    the wire and reattaches UTC on the way out, on every backend.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _table_args(*args):
    """Combine per-table constraints with the schema kwarg (Postgres only)."""
    if IS_POSTGRES:
        return (*args, {"schema": L360_SCHEMA})
    return args if args else {}


def _fk(target: str) -> str:
    """Schema-qualify a ForeignKey target on Postgres; plain on SQLite."""
    return f"{L360_SCHEMA}.{target}" if IS_POSTGRES else target


class EducatorLevel(Base):
    __tablename__ = "educator_levels"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # "admin" | "educator"
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="educator")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Educators carry a level (drives pricing/pay); admins have none.
    level_id: Mapped[int | None] = mapped_column(
        ForeignKey(_fk("educator_levels.id")), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow
    )


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guardian_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Free-text reference to the child (initials/nickname) — not a full record.
    child_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow
    )


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PriceListEntry(Base):
    """Dated price tiers: never edited in place — new rows with a later
    valid_from supersede older ones. All money is integer cents (EUR)."""

    __tablename__ = "price_list_entries"
    __table_args__ = _table_args(
        UniqueConstraint(
            "level_id", "duration_minutes", "valid_from",
            name="uq_price_level_duration_validfrom",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level_id: Mapped[int] = mapped_column(
        ForeignKey(_fk("educator_levels.id")), nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # 60|90|120
    client_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    educator_rate_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)


class FacilityHours(Base):
    __tablename__ = "facility_hours"
    __table_args__ = _table_args(
        UniqueConstraint("weekday", name="uq_facility_hours_weekday"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 0 = Monday .. 6 = Sunday (Python datetime.weekday() convention).
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    open_time: Mapped[time] = mapped_column(Time, nullable=False)
    close_time: Mapped[time] = mapped_column(Time, nullable=False)


class FacilityClosure(Base):
    __tablename__ = "facility_closures"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    # Null room = the whole facility is closed that day.
    room_id: Mapped[int | None] = mapped_column(ForeignKey(_fk("rooms.id")), nullable=True)


class BookingSeries(Base):
    """A weekly recurring slot; individual occurrences materialise as Bookings."""

    __tablename__ = "booking_series"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey(_fk("rooms.id")), nullable=False)
    educator_id: Mapped[int] = mapped_column(ForeignKey(_fk("users.id")), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey(_fk("clients.id")), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon .. 6=Sun
    # Wall-clock start in Europe/Malta local time.
    local_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow
    )


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = _table_args(
        Index("ix_bookings_room_start", "room_id", "start_utc"),
        Index("ix_bookings_educator_start", "educator_id", "start_utc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey(_fk("rooms.id")), nullable=False)
    educator_id: Mapped[int] = mapped_column(ForeignKey(_fk("users.id")), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey(_fk("clients.id")), nullable=False)
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey(_fk("booking_series.id")), nullable=True
    )
    start_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # confirmed | completed | cancelled | cancelled_late | no_show
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey(_fk("users.id")), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )


class NotificationLog(Base):
    """One row per email actually sent. `dedupe_key` is unique so a retried
    request, or two scheduler workers racing on the same reminder, can
    never send the same notification twice — the loser's insert just fails
    the unique constraint and is treated as "already sent"."""

    __tablename__ = "notification_logs"
    __table_args__ = _table_args(
        UniqueConstraint("dedupe_key", name="uq_notification_dedupe_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey(_fk("bookings.id")), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey(_fk("users.id")), nullable=True)
    # confirmation | change | cancel | reminder_24h | digest
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)


class Invoice(Base):
    """A monthly (or custom-period) client invoice. VAT-exempt: no tax
    lines anywhere. Numbers are assigned only at issue time, sequentially,
    and never reused. `void` status is defined but corrections
    (e.g. a credit note flow) aren't built yet — see l360/README.md."""

    __tablename__ = "invoices"
    __table_args__ = _table_args(
        UniqueConstraint("number", name="uq_invoice_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey(_fk("clients.id")), nullable=False)
    # Null until issued — draft invoices have no number yet.
    number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    # draft | issued | paid | partially_paid | void
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issued_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey(_fk("users.id")), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey(_fk("invoices.id")), nullable=False)
    # Nullable so a manual/adjustment line is possible; a booking-derived
    # line always sets this, and it's how "already invoiced" is checked —
    # a booking is billable only if no InvoiceLine references it yet.
    booking_id: Mapped[int | None] = mapped_column(ForeignKey(_fk("bookings.id")), nullable=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)


class BankTxn(Base):
    """A raw imported transaction row from Revolut Business (or any future
    provider). Kept verbatim + idempotent on external_id so re-running the
    sync never creates duplicates; matching is a separate step recorded on
    Payment, not mutation of this row (beyond linking payment_id)."""

    __tablename__ = "bank_txns"
    __table_args__ = _table_args(
        UniqueConstraint("external_id", name="uq_bank_txn_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    txn_date: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(300), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey(_fk("payments.id")), nullable=True)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey(_fk("invoices.id")), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # revolut_transfer | bank_transfer | cash
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    # auto | manual
    match_status: Mapped[str] = mapped_column(String(10), nullable=False, default="manual")
    created_by: Mapped[int | None] = mapped_column(ForeignKey(_fk("users.id")), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)


class CalendarToken(Base):
    """One revocable, unguessable token per user for their read-only iCal
    feed. The token itself IS the auth for that endpoint (calendar apps
    can't do cookie/session login), so it must be long and random, and
    revoking it (rather than the user's password) is how a leaked feed
    URL gets cut off without touching their login."""

    __tablename__ = "calendar_tokens"
    __table_args__ = _table_args(
        UniqueConstraint("token", name="uq_calendar_token"),
        UniqueConstraint("user_id", name="uq_calendar_token_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(_fk("users.id")), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
