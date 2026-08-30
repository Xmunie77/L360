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


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


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
    # pending | submitted | None — educator onboarding form status (always
    # None for admins and for accounts predating the feature).
    onboarding_status: str | None = None


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

    @model_validator(mode="after")
    def _normalise(self) -> "EmailSettingsIn":
        # Browsers love turning a pasted hostname into a URL, and Google
        # shows app passwords with spaces — both broke the first real setup
        # (30/08/2026), so normalise here instead of failing at send time.
        host = self.host.strip()
        for prefix in ("http://", "https://", "smtp://"):
            if host.lower().startswith(prefix):
                host = host[len(prefix):]
        self.host = host.rstrip("/")
        if self.password:
            self.password = self.password.replace(" ", "")
        return self


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


class InvoiceSettingsIn(BaseModel):
    """Admin → Invoicing: the letterhead printed on every client invoice.
    Blank fields revert to the built-in defaults. Address/bank/contact are
    multiline (one line per row on the PDF)."""

    name: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=500)
    vat: str = Field(default="", max_length=200)
    bank: str = Field(default="", max_length=500)
    contact: str = Field(default="", max_length=300)
    footer: str = Field(default="", max_length=1000)


class InvoiceSettingsOut(BaseModel):
    name: str
    address: str
    vat: str
    bank: str
    contact: str
    footer: str


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


# --- educator onboarding ---------------------------------------------------
class QualificationRow(BaseModel):
    qualification: str = Field(default="", max_length=200)
    institution: str = Field(default="", max_length=200)
    year: str = Field(default="", max_length=20)
    level_result: str = Field(default="", max_length=100)


class ExperienceRow(BaseModel):
    organisation: str = Field(default="", max_length=200)
    role_subjects: str = Field(default="", max_length=200)
    learner_ages: str = Field(default="", max_length=100)
    from_when: str = Field(default="", max_length=50)
    to_when: str = Field(default="", max_length=50)


class AvailabilityRow(BaseModel):
    day: str = Field(max_length=12)
    available_from: str = Field(default="", max_length=20)
    available_until: str = Field(default="", max_length=20)
    on_site: bool = False
    online: bool = False
    notes: str = Field(default="", max_length=300)


class RefereeIn(BaseModel):
    name_position: str = Field(default="", max_length=200)
    organisation: str = Field(default="", max_length=200)
    relationship: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=50)
    known_since: str = Field(default="", max_length=50)
    contact_now: bool | None = None
    contact_after: str = Field(default="", max_length=100)


class EducatorOnboardingSubmitIn(BaseModel):
    """The educator's completed questionnaire — in-app version of the paper
    "Educator Onboarding Form" v1.0. Mandatory: identity/contact basics,
    right-to-work answer, emergency contact, all four safeguarding
    declarations, all five professional-boundary acknowledgements, referee
    authorisation, the two data-protection confirmations, and the signed
    declaration. Everything else mirrors the paper form's "mark N/A"
    tolerance and is optional."""

    # 1. Application overview
    role_applied_for: str = Field(default="", max_length=200)
    subjects_services: str = Field(default="", max_length=300)
    preferred_start_date: str = Field(default="", max_length=50)
    engagement_type: Literal["employee", "self_employed", "sessional", "tbc"] = "tbc"
    referred_by: str = Field(default="", max_length=200)
    existing_contact: str = Field(default="", max_length=200)

    # 2. Personal and contact details
    full_legal_name: str = Field(min_length=1, max_length=200)
    preferred_name: str = Field(default="", max_length=200)
    former_names: str = Field(default="", max_length=200)
    date_of_birth: date
    id_passport_number: str = Field(min_length=1, max_length=50)
    nationality: str = Field(default="", max_length=100)
    residential_address: str = Field(min_length=1, max_length=500)
    postcode_country: str = Field(default="", max_length=100)
    mobile: str = Field(min_length=1, max_length=50)
    email: EmailStr
    preferred_contact: Literal["phone", "email", "whatsapp"] = "email"
    right_to_work: Literal["yes", "no", "pending"]
    permit_basis: Literal["maltese_eu", "single_permit", "other", ""] = ""
    permit_basis_other: str = Field(default="", max_length=200)
    permit_number: str = Field(default="", max_length=100)
    permit_expiry: str = Field(default="", max_length=50)

    # 3. Emergency contact and health
    emergency_name: str = Field(min_length=1, max_length=200)
    emergency_relationship: str = Field(default="", max_length=100)
    emergency_phone: str = Field(min_length=1, max_length=50)
    emergency_alt_phone: str = Field(default="", max_length=50)
    medical_conditions: str = Field(default="", max_length=1000)
    medication_action: str = Field(default="", max_length=1000)
    accessibility_needs: str = Field(default="", max_length=1000)

    # 4. Education / qualifications
    qualifications: list[QualificationRow] = Field(default_factory=list, max_length=10)
    credentials: list[str] = Field(default_factory=list, max_length=20)
    warrant_number: str = Field(default="", max_length=100)
    issuing_body: str = Field(default="", max_length=200)
    warrant_expiry: str = Field(default="", max_length=50)
    languages_spoken: str = Field(default="", max_length=300)
    languages_taught: str = Field(default="", max_length=300)

    # 5. Experience
    experience: list[ExperienceRow] = Field(default_factory=list, max_length=10)
    experience_areas: list[str] = Field(default_factory=list, max_length=20)
    teaching_profile: str = Field(default="", max_length=3000)
    subjects_levels_boards: str = Field(default="", max_length=2000)
    inclusive_approach: str = Field(default="", max_length=3000)

    # 6. Digital skills
    digital_skills: list[str] = Field(default_factory=list, max_length=20)
    own_device: bool | None = None
    reliable_internet: bool | None = None
    other_software: str = Field(default="", max_length=500)

    # 7. Availability
    availability: list[AvailabilityRow] = Field(default_factory=list, max_length=7)
    min_hours_weekly: str = Field(default="", max_length=20)
    max_hours_weekly: str = Field(default="", max_length=20)
    holidays_available: Literal["yes", "no", "some", ""] = ""
    notice_needed: str = Field(default="", max_length=200)
    unavailable_dates: str = Field(default="", max_length=500)
    preferred_ages: str = Field(default="", max_length=200)
    preferred_locations: str = Field(default="", max_length=200)
    willing_travel: Literal["yes", "no", "within", ""] = ""
    travel_within: str = Field(default="", max_length=200)
    own_transport: Literal["yes", "no", "na", ""] = ""

    # 8. Session preferences
    session_preferences: list[str] = Field(default_factory=list, max_length=10)
    session_restrictions: str = Field(default="", max_length=1000)

    # 9. Safeguarding — all four must be answered; "yes" is allowed and
    # assessed fairly, but blank is not.
    sg_convicted: Literal["no", "yes"]
    sg_proceedings: Literal["no", "yes"]
    sg_dismissed: Literal["no", "yes"]
    sg_other_matters: Literal["no", "yes"]
    sg_documents: list[str] = Field(default_factory=list, max_length=10)
    clearance_date: str = Field(default="", max_length=50)
    clearance_reference: str = Field(default="", max_length=100)
    clearance_renewal: str = Field(default="", max_length=50)
    b_follow_procedures: bool
    b_report_concerns: bool
    b_approved_channels: bool
    b_no_sharing: bool
    b_boundaries: bool

    # 10. References
    referee1: RefereeIn = Field(default_factory=RefereeIn)
    referee2: RefereeIn = Field(default_factory=RefereeIn)
    referee_authorisation: bool

    # 11. Payment and tax
    payment_basis: Literal["payroll", "self_invoice", "other", ""] = ""
    payment_basis_other: str = Field(default="", max_length=200)
    tax_vat_number: str = Field(default="", max_length=100)
    social_security_number: str = Field(default="", max_length=100)
    business_name: str = Field(default="", max_length=200)
    invoice_email: str = Field(default="", max_length=255)
    bank_account_holder: str = Field(default="", max_length=200)
    iban: str = Field(default="", max_length=50)
    bic: str = Field(default="", max_length=20)

    # 12. Policies
    policies_ack: list[str] = Field(default_factory=list, max_length=20)

    # 13. Data protection
    dp_accuracy: bool
    dp_processing: bool
    dp_marketing: bool = False
    dp_queries: str = Field(default="", max_length=1000)

    # 14. Declaration
    signature_name: str = Field(min_length=1, max_length=200)
    signed_date: date

    @model_validator(mode="after")
    def _check(self) -> "EducatorOnboardingSubmitIn":
        problems = []
        if not all([self.b_follow_procedures, self.b_report_concerns, self.b_approved_channels,
                    self.b_no_sharing, self.b_boundaries]):
            problems.append("all five professional-boundaries acknowledgements")
        if not self.referee_authorisation:
            problems.append("the referee-contact authorisation")
        if not self.dp_accuracy or not self.dp_processing:
            problems.append("the data-protection confirmations")
        if problems:
            raise ValueError("Please agree to " + ", ".join(problems) + ".")
        return self


class ChecklistItemIn(BaseModel):
    status: Literal["pending", "complete", "na"] = "pending"
    checked_by: str = Field(default="", max_length=200)
    date: str = Field(default="", max_length=50)


class ChecklistApprovalIn(BaseModel):
    educator_ref: str = Field(default="", max_length=100)
    approved_roles: str = Field(default="", max_length=300)
    approved_locations: str = Field(default="", max_length=300)
    sg_restrictions: str = Field(default="", max_length=500)
    start_date: str = Field(default="", max_length=50)
    approved_by: str = Field(default="", max_length=200)
    signature: str = Field(default="", max_length=200)
    approval_date: str = Field(default="", max_length=50)


class EducatorChecklistIn(BaseModel):
    """The admin-side section-15 internal checklist (paper form v1.0).
    Item keys must come from educator_onboarding.CHECKLIST_ITEMS."""

    items: dict[str, ChecklistItemIn] = Field(default_factory=dict)
    approval: ChecklistApprovalIn = Field(default_factory=ChecklistApprovalIn)

    @model_validator(mode="after")
    def _known_keys(self) -> "EducatorChecklistIn":
        from l360.educator_onboarding import CHECKLIST_ITEMS

        unknown = [k for k in self.items if k not in CHECKLIST_ITEMS]
        if unknown:
            raise ValueError(f"Unknown checklist item(s): {', '.join(unknown)}")
        return self


class EducatorOnboardingPrefillOut(BaseModel):
    status: str
    full_name: str
    email: str


class EducatorOnboardingAdminOut(BaseModel):
    id: int
    user_id: int
    status: str
    source: str
    link: str
    sent_at: datetime | None
    submitted_at: datetime | None
    signature_name: str | None
    signed_date: date | None
    answers: dict | None
    # Section-15 internal checklist + approval (admin-side; never public).
    internal: dict | None


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
    # Locked in at booking time (and re-locked on a move that changes the
    # service type) — not a live lookup, so a later price-list edit never
    # changes what an existing booking is billed at.
    client_price_cents: int | None
    tutor_payment_cents: int | None
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
