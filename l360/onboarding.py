"""Client onboarding questionnaire — shared logic.

The questionnaire replaces the legacy Google "Client Onboarding Form": when an
admin adds a client with the guardian's basic details, an OnboardingForm row is
created with an unguessable token and the link is emailed to the guardian, who
completes it without an account (the token IS the auth, same pattern as the
iCal CalendarToken). Admins can also fill the same fields directly in the OS.

Used by api.py (public + admin routes) and import_form_responses.py (which
backfills submitted forms from the Google Sheet responses export).
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from l360 import notify
from l360.config import PUBLIC_BASE_URL
from l360.models import Client, NotificationLog, OnboardingForm

# Consents that MUST be "yes" for a submission to be accepted — the service
# can't be provided without them. marketing_opt_in is the only optional one.
REQUIRED_CONSENTS = {
    "fee_undertaking": "the fee payment undertaking",
    "termination_60d_ack": "the 60-day payment termination policy",
    "info_storage_consent": "the information storage and tutor sharing consent",
    "epinephrine_ack": "the allergy medication acknowledgement",
    "accident_ack": "the accident liability acknowledgement",
    "cancellation_policy_ack": "the cancellation policy",
    "illness_policy_ack": "the illness policy",
}

# Client columns the questionnaire owns. Submission overwrites these from the
# form (the guardian's answers are authoritative for their own details);
# admin-only fields (observations, notes, active) are never touched.
CLIENT_FIELDS = (
    "guardian_first_name",
    "guardian_surname",
    "email",
    "phone",
    "guardian_id_number",
    "guardian2_name",
    "guardian2_id_number",
    "guardian2_email",
    "guardian2_phone",
    "child_name",
    "child_dob",
    "school",
    "address",
    "has_allergies",
    "allergy_details",
)

CONSENT_FIELDS = (
    "fee_undertaking",
    "termination_60d_ack",
    "info_storage_consent",
    "marketing_opt_in",
    "epinephrine_ack",
    "accident_ack",
    "cancellation_policy_ack",
    "illness_policy_ack",
)


def get_or_create_form(db: Session, client: Client) -> OnboardingForm:
    form = db.scalar(select(OnboardingForm).where(OnboardingForm.client_id == client.id))
    if form is None:
        form = OnboardingForm(client_id=client.id, token=secrets.token_urlsafe(32))
        db.add(form)
        db.flush()
    return form


def form_link(form: OnboardingForm) -> str:
    return f"{PUBLIC_BASE_URL}/?onboarding={form.token}"


def send_invite(db: Session, client: Client, form: OnboardingForm) -> bool:
    """Email the questionnaire link to the guardian. Safe to call repeatedly:
    each call is a distinct send (the dedupe key includes a per-form send
    counter), so an explicit admin "resend" goes out again, while a retried
    request racing itself can still only send once per counter value."""
    if not client.email or form.status == "submitted":
        return False
    prior_sends = db.scalar(
        select(func.count())
        .select_from(NotificationLog)
        .where(NotificationLog.kind == "onboarding_invite", NotificationLog.dedupe_key.like(f"onboarding_invite:{form.id}:%"))
    ) or 0
    link = form_link(form)
    sent = notify.send_once(
        db,
        to=client.email,
        subject="Welcome to Learning 360° — your onboarding form",
        body=(
            f"Dear {client.guardian_first_name} {client.guardian_surname},\n\n"
            "Welcome to Learning 360° Foundation.\n\n"
            "To complete your registration, please fill in our client onboarding "
            "form — it covers your contact details, your learner's details, and "
            "our policies, and takes about five minutes:\n\n"
            f"{link}\n\n"
            "Your information is stored securely by Learning 360° Foundation and "
            "is never shared with third parties.\n\n"
            "If anything in the form is unclear, just reply to this email.\n\n"
            "Warm regards,\n"
            "Learning 360° Foundation\n"
            "Swatar, Malta"
        ),
        booking_id=None,
        user_id=None,
        kind="onboarding_invite",
        dedupe_key=f"onboarding_invite:{form.id}:{prior_sends}",
    )
    if sent:
        form.sent_at = datetime.now(UTC)
        db.commit()
    return sent


def apply_submission(db: Session, client: Client, form: OnboardingForm, data, *, source: str = "app", submitted_at: datetime | None = None) -> None:
    """Write a completed questionnaire onto the client + the form's consent
    record and mark it submitted. `data` is any object carrying the
    CLIENT_FIELDS + CONSENT_FIELDS + signature attributes (the Pydantic
    submit schema, or the importer's parsed row)."""
    for field in CLIENT_FIELDS:
        setattr(client, field, getattr(data, field))
    for field in CONSENT_FIELDS:
        setattr(form, field, getattr(data, field))
    form.signature_guardian1 = data.signature_guardian1
    form.signature_guardian2 = data.signature_guardian2
    form.signed_date = data.signed_date
    form.status = "submitted"
    form.source = source
    form.submitted_at = submitted_at or datetime.now(UTC)
    db.commit()
