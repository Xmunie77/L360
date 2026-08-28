"""Pydantic v2 request/response models for the l360 API."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


# --- auth ---------------------------------------------------------------
class LoginReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=200)


class MeResp(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    level_id: int | None = None


# --- educator levels ------------------------------------------------------
class EducatorLevelIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sort_order: int = 0
    active: bool = True


class EducatorLevelOut(EducatorLevelIn):
    id: int


# --- rooms -----------------------------------------------------------------
class RoomIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sort_order: int = 0
    active: bool = True


class RoomOut(RoomIn):
    id: int


# --- users (educators/admins) ----------------------------------------------
class UserIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: str = Field(pattern="^(admin|educator)$")
    level_id: int | None = None
    password: str = Field(min_length=8, max_length=200)


class UserUpdate(BaseModel):
    full_name: str | None = None
    level_id: int | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    level_id: int | None
    active: bool


# --- clients -----------------------------------------------------------
class ClientIn(BaseModel):
    guardian_first_name: str = Field(min_length=1, max_length=100)
    guardian_surname: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = None
    child_name: str | None = None
    child_dob: date | None = None
    # Onboarding notes on the child's needs (e.g. dyslexia, Down syndrome).
    observations: str | None = None
    notes: str | None = None
    active: bool = True


class ClientOut(ClientIn):
    id: int


class ClientBrief(BaseModel):
    """Minimal shape for non-admin lists — no notes/phone/DOB/observations exposed."""
    id: int
    guardian_first_name: str
    guardian_surname: str
    child_name: str | None


# --- price list -----------------------------------------------------------
class PriceListEntryIn(BaseModel):
    level_id: int
    duration_minutes: int = Field(pattern=None)
    client_price_cents: int = Field(ge=0)
    educator_rate_cents: int = Field(ge=0)
    valid_from: date


class PriceListEntryOut(PriceListEntryIn):
    id: int


# --- facility hours / closures --------------------------------------------
class FacilityHoursIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    open_time: time
    close_time: time


class FacilityHoursOut(FacilityHoursIn):
    id: int


class FacilityClosureIn(BaseModel):
    date: date
    reason: str = Field(min_length=1, max_length=300)
    room_id: int | None = None


class FacilityClosureOut(FacilityClosureIn):
    id: int


# --- bookings -----------------------------------------------------------
Duration = Literal[60, 90, 120]


class NextAvailableOut(BaseModel):
    room_id: int
    room_name: str
    start_utc: datetime


class BookingIn(BaseModel):
    room_id: int
    educator_id: int
    client_id: int
    start_utc: datetime
    duration_minutes: Duration
    notes: str | None = None


class BookingSeriesIn(BaseModel):
    room_id: int
    educator_id: int
    client_id: int
    weekday: int = Field(ge=0, le=6)
    local_time: time
    duration_minutes: Duration
    starts_on: date
    ends_on: date
    # 1 = every week, 2 = every other week (fortnightly).
    interval_weeks: int = Field(default=1, ge=1, le=2)
    notes: str | None = None


class BookingMoveIn(BaseModel):
    start_utc: datetime | None = None
    room_id: int | None = None
    duration_minutes: Duration | None = None
    notes: str | None = None


class BookingStatusIn(BaseModel):
    status: Literal["completed", "no_show"]


class BookingOut(BaseModel):
    id: int
    room_id: int
    room_name: str
    educator_id: int
    educator_name: str
    client_id: int
    client_label: str
    series_id: int | None
    start_utc: datetime
    duration_minutes: int
    status: str
    notes: str | None
    created_by: int
    created_at: datetime
    cancelled_at: datetime | None


class SkippedOccurrence(BaseModel):
    date: date
    reason: str


class BookingSeriesOut(BaseModel):
    series_id: int
    created: list[BookingOut]
    skipped: list[SkippedOccurrence]


# --- billing -----------------------------------------------------------
class BillingRunIn(BaseModel):
    period_start: date
    period_end: date


class InvoiceLineOut(BaseModel):
    id: int
    booking_id: int | None
    description: str
    unit_price_cents: int
    quantity: int
    amount_cents: int


class InvoiceOut(BaseModel):
    id: int
    client_id: int
    client_label: str
    number: str | None
    period_start: date
    period_end: date
    status: str
    total_cents: int
    outstanding_cents: int
    issued_at: datetime | None
    due_date: date | None
    notes: str | None
    created_at: datetime


class InvoiceDetailOut(InvoiceOut):
    lines: list[InvoiceLineOut]


class BillingRunOut(BaseModel):
    created: list[InvoiceOut]
    skipped_clients: list[int]  # clients with nothing billable this period


# --- payments / reconciliation --------------------------------------------
class SyncResultOut(BaseModel):
    imported: int
    matched: int
    unmatched: int


class BankTxnOut(BaseModel):
    id: int
    external_id: str
    txn_date: datetime
    amount_cents: int
    currency: str
    reference: str | None
    counterparty: str | None
    payment_id: int | None


class ManualMatchIn(BaseModel):
    bank_txn_id: int
    invoice_id: int


class RecordPaymentIn(BaseModel):
    invoice_id: int
    amount_cents: int = Field(gt=0)
    method: Literal["bank_transfer", "cash"]
    received_at: datetime
    external_ref: str | None = None


class PaymentOut(BaseModel):
    id: int
    invoice_id: int
    amount_cents: int
    method: str
    external_ref: str | None
    received_at: datetime
    match_status: str


# --- statements / reports ------------------------------------------------
class PeriodQuery(BaseModel):
    period_start: date
    period_end: date


class StatementInvoiceLineOut(BaseModel):
    id: int
    number: str | None
    status: str
    total_cents: int
    issued_at: datetime | None


class StatementPaymentLineOut(BaseModel):
    id: int
    amount_cents: int
    method: str
    received_at: datetime


class ClientStatementOut(BaseModel):
    client_id: int
    client_label: str
    period_start: date
    period_end: date
    opening_balance_cents: int
    invoices: list[StatementInvoiceLineOut]
    payments: list[StatementPaymentLineOut]
    closing_balance_cents: int


class SummarySessionLineOut(BaseModel):
    booking_id: int
    local_date: date
    client_label: str
    duration_minutes: int
    status: str
    rate_cents: int


class EducatorSummaryOut(BaseModel):
    educator_id: int
    educator_name: str
    period_start: date
    period_end: date
    sessions: list[SummarySessionLineOut]
    total_payable_cents: int


class RoomUtilisationOut(BaseModel):
    room_id: int
    room_name: str
    session_count: int
    booked_minutes: int


class CalendarTokenOut(BaseModel):
    token: str
    feed_path: str
