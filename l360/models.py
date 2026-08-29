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
    guardian_first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    guardian_surname: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    guardian_id_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Second parent/guardian — optional, single free-text name (the
    # onboarding form asks "name and surname" as one field).
    guardian2_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    guardian2_id_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    guardian2_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guardian2_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    child_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    child_dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    school: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Tri-state: None = not yet answered on the onboarding form.
    # Allergy details are health data (special-category under GDPR) —
    # admins only, same handling as `observations`.
    has_allergies: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    allergy_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Onboarding notes on the child's needs (e.g. dyslexia, Down syndrome) —
    # special-category data under GDPR; visible to admins only.
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow
    )

    @property
    def guardian_name(self) -> str:
        return f"{self.guardian_first_name} {self.guardian_surname}"


class OnboardingForm(Base):
    """The client-onboarding questionnaire — one per client. Created (with an
    unguessable token) when the client is added; the token link is emailed to
    the guardian, who fills the form without an account (the token itself is
    the auth, same pattern as CalendarToken). Consent/acknowledgement answers
    and typed signatures live HERE, not on Client — they're a point-in-time
    legal record of what was agreed, kept even as the client's details evolve.

    All consent fields are tri-state: None = not yet answered. The submit
    endpoint requires the mandatory ones to be true; `marketing_opt_in` is
    the only genuinely optional consent (an honest no is stored as False).
    """

    __tablename__ = "onboarding_forms"
    __table_args__ = _table_args(
        UniqueConstraint("token", name="uq_onboarding_token"),
        UniqueConstraint("client_id", name="uq_onboarding_client"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey(_fk("clients.id")), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    # pending | submitted
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # app (filled via the emailed link / by an admin) | google_form (imported
    # from the legacy Google Form responses sheet).
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="app")
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    # Payment + data consents (must be true to submit, except marketing).
    fee_undertaking: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    termination_60d_ack: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    info_storage_consent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    marketing_opt_in: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Liability acknowledgements + policies.
    epinephrine_ack: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    accident_ack: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cancellation_policy_ack: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    illness_policy_ack: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Typed signatures (the Google Form did the same — typed full names).
    signature_guardian1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signature_guardian2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

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


class ServiceType(Base):
    """A priced offering outside the level/duration session-price model —
    named meetings, programmes and one-off items from the foundation's own
    price list, each with a flat client price and tutor/educator payment
    (the difference is the foundation's contribution). "session" items are
    delivered as a booked session; "additional_service" items (flashcards,
    etc.) are not calendar bookings."""

    __tablename__ = "service_types"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # "session" | "additional_service"
    client_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    tutor_payment_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # Some sessions happen off-site (home/school visits) and never occupy a
    # facility room; additional services aren't bookings at all.
    requires_room: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
    # Nullable at the DB level for older rows created before this column
    # existed; the API requires it on every new series.
    service_type_id: Mapped[int | None] = mapped_column(ForeignKey(_fk("service_types.id")), nullable=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon .. 6=Sun
    # Wall-clock start in Europe/Malta local time.
    local_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    # 1 = every week, 2 = every other week (fortnightly).
    interval_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
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
    # What's being billed — a named item from the L360 price list (e.g.
    # "Consultant Office Session"). Nullable at the DB level for older rows
    # created before this column existed; the API requires it on every new
    # booking, and billing/statements price from here, not from
    # educator level + duration.
    service_type_id: Mapped[int | None] = mapped_column(ForeignKey(_fk("service_types.id")), nullable=True)
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


class PasswordResetToken(Base):
    """Single-use, time-limited token for the forgot-password flow. Each
    request invalidates any prior unused token for that user (at most one
    live token per user), so an old emailed link can't be replayed once a
    newer reset has been requested."""

    __tablename__ = "password_reset_tokens"
    __table_args__ = _table_args(
        UniqueConstraint("token", name="uq_password_reset_token"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(_fk("users.id")), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
