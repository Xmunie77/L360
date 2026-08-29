"""Pydantic v2 request/response models for the l360 API."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


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


# --- service types (named sessions/additional services outside the
# level+duration price list) --------------------------------------------
class ServiceTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: Literal["session", "additional_service"]
    client_price_cents: int = Field(ge=0)
    tutor_payment_cents: int = Field(ge=0)
    requires_room: bool = True
    sort_order: int = 0
    active: bool = True


class ServiceTypeOut(ServiceTypeIn):
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
    guardian_id_number: str | None = Field(default=None, max_length=50)
    guardian2_name: str | None = Field(default=None, max_length=200)
    guardian2_id_number: str | None = Field(default=None, max_length=50)
    guardian2_email: str | None = Field(default=None, max_length=255)
    guardian2_phone: str | None = Field(default=None, max_length=50)
    child_name: str | None = None
    child_dob: date | None = None
    school: str | None = Field(default=None, max_length=200)
    address: str | None = None
    # Tri-state: None = the allergies question hasn't been answered yet.
    has_allergies: bool | None = None
    allergy_details: str | None = None
    # Onboarding notes on the child's needs (e.g. dyslexia, Down syndrome).
    observations: str | None = None
    notes: str | None = None
    active: bool = True


class ClientOut(ClientIn):
    id: int
    # pending | submitted | None (no onboarding form created yet — e.g. a
    # client added before this feature existed).
    onboarding_status: str | None = None


class EmailSettingsIn(BaseModel):
    """Admin → Email settings. Blank host/port/user/from reverts that field
    to the env-var fallback; password is write-only — blank/omitted keeps
    the stored one, so re-saving the form never wipes it."""

    host: str = Field(default="", max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    user: str = Field(default="", max_length=255)
    email_from: str = Field(default="", max_length=255)
    password: str | None = Field(default=None, max_length=255)


class EmailSettingsOut(BaseModel):
    host: str
    port: int
    user: str
    email_from: str
    # Whether a password is available (DB or env) — the password itself is
    # never returned by the API.
    password_set: bool


class EmailTestOut(BaseModel):
    ok: bool
    detail: str


class OnboardingPrefillOut(BaseModel):
    """What the public questionnaire page gets for a valid token: the form
    status plus the client details already on record (entered by the admin,
    or from an earlier partial save) so the guardian doesn't retype them.
    Never includes admin-only fields (observations, notes)."""

    status: str
    guardian_first_name: str
    guardian_surname: str
    email: str
    phone: str | None
    guardian_id_number: str | None
    guardian2_name: str | None
    guardian2_id_number: str | None
    guardian2_email: str | None
    guardian2_phone: str | None
    child_name: str | None
    child_dob: date | None
    school: str | None
    address: str | None
    has_allergies: bool | None
    allergy_details: str | None


class OnboardingSubmitIn(BaseModel):
    """The guardian's completed questionnaire. Field-level requirements mirror
    the original Google Form: guardian 2 and school are optional, everything
    else is required — including every consent except marketing_opt_in, which
    is a genuine choice (an honest "no" is stored)."""

    guardian_first_name: str = Field(min_length=1, max_length=100)
    guardian_surname: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=1, max_length=50)
    guardian_id_number: str = Field(min_length=1, max_length=50)
    guardian2_name: str | None = Field(default=None, max_length=200)
    guardian2_id_number: str | None = Field(default=None, max_length=50)
    guardian2_email: str | None = Field(default=None, max_length=255)
    guardian2_phone: str | None = Field(default=None, max_length=50)
    child_name: str = Field(min_length=1, max_length=200)
    child_dob: date
    school: str | None = Field(default=None, max_length=200)
    address: str = Field(min_length=1)
    has_allergies: bool
    allergy_details: str | None = None

    fee_undertaking: bool
    termination_60d_ack: bool
    info_storage_consent: bool
    marketing_opt_in: bool
    epinephrine_ack: bool
    accident_ack: bool
    cancellation_policy_ack: bool
    illness_policy_ack: bool

    signature_guardian1: str = Field(min_length=1, max_length=200)
    signature_guardian2: str | None = Field(default=None, max_length=200)
    signed_date: date

    @model_validator(mode="after")
    def _check(self) -> "OnboardingSubmitIn":
        from l360.onboarding import REQUIRED_CONSENTS

        missing = [label for field, label in REQUIRED_CONSENTS.items() if getattr(self, field) is not True]
        if missing:
            raise ValueError("Please agree to " + ", ".join(missing) + ".")
        if self.has_allergies and not (self.allergy_details or "").strip():
            raise ValueError("Please specify the learner's allergies.")
        return self


class OnboardingAdminOut(BaseModel):
    """Full onboarding-form record for the admin client-detail page."""

    id: int
    client_id: int
    status: str
    source: str
    link: str
    sent_at: datetime | None
    submitted_at: datetime | None
    fee_undertaking: bool | None
    termination_60d_ack: bool | None
    info_storage_consent: bool | None
    marketing_opt_in: bool | None
    epinephrine_ack: bool | None
    accident_ack: bool | None
    cancellation_policy_ack: bool | None
    illness_policy_ack: bool | None
    signature_guardian1: str | None
    signature_guardian2: str | None
    signed_date: date | None


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
    room_id: int | None = None
    room_name: str | None = None
    start_utc: datetime | None = None
    # Set (and the room_* fields left null) when nothing was found, so the
    # UI can tell "no facility hours configured yet" apart from "genuinely
    # fully booked" instead of showing one flat "nothing available".
    reason: Literal["no_facility_hours", "fully_booked"] | None = None


class BookingIn(BaseModel):
    room_id: int
    educator_id: int
    client_id: int
    # What's being billed — a named "session" item from the L360 price list
    # (service_types), not educator level + duration.
    service_type_id: int
    start_utc: datetime
    duration_minutes: Duration
    notes: str | None = None


class BookingSeriesIn(BaseModel):
    room_id: int
    educator_id: int
    client_id: int
    service_type_id: int
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
    service_type_id: int | None = None
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
    service_type_id: int | None
    service_type_name: str | None
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
    service_type_name: str | None
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
