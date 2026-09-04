"""Educator onboarding questionnaire — shared logic.

Staff-side sibling of onboarding.py: when an admin adds an educator account,
an EducatorOnboardingForm row is created with an unguessable token and the
link is emailed, so the educator completes the full onboarding form (the
in-app version of the paper "Educator Onboarding Form" v1.0) before their
first session. The token is the auth — no sign-in needed, same pattern as
the client form and the iCal feed.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from l360 import email_templates, notify
from l360.config import PUBLIC_BASE_URL
from l360.models import EducatorOnboardingForm, NotificationLog, User


# Section 15 of the paper form — the internal onboarding checklist. Key →
# label; the schema validates submitted checklist keys against this set.
# "Do not schedule unsupervised learner contact until all mandatory checks
# for the role are complete and authorised."
CHECKLIST_ITEMS = {
    "application_reviewed": "Application reviewed and role confirmed",
    "interview": "Interview completed",
    "identity": "Identity verified against original",
    "right_to_work": "Right to work verified",
    "qualifications": "Qualifications / warrant verified",
    "police_cert": "Police conduct certificate reviewed",
    "minors_clearance": "Applicable minors / safeguarding clearance completed",
    "references": "Two references received and satisfactory",
    "employment_status": "Employment status confirmed",
    "contract": "Contract / service agreement signed",
    "rate_approved": "Rate and payment terms approved",
    "payroll_setup": "Payroll / supplier setup completed",
    "emergency_contact": "Emergency contact recorded",
    "sg_induction": "Safeguarding induction completed",
    "policies_issued": "Policies issued and acknowledgements received",
    "it_access": "IT / system access approved",
    "timetable": "Timetable, location and reporting line confirmed",
    "data_access": "Data access restricted to role requirements",
}


def get_or_create_form(db: Session, user: User) -> EducatorOnboardingForm:
    form = db.scalar(select(EducatorOnboardingForm).where(EducatorOnboardingForm.user_id == user.id))
    if form is None:
        form = EducatorOnboardingForm(user_id=user.id, token=secrets.token_urlsafe(32))
        db.add(form)
        db.flush()
    return form


def form_link(form: EducatorOnboardingForm) -> str:
    return f"{PUBLIC_BASE_URL}/?educator-onboarding={form.token}"


def send_invite(db: Session, user: User, form: EducatorOnboardingForm) -> bool:
    """Email the questionnaire link to the educator. Same repeat-send
    semantics as the client invite: each explicit send goes out (per-form
    send counter in the dedupe key), a racing retry of the same send can't
    double-fire."""
    if not user.email or form.status == "submitted":
        return False
    prior_sends = db.scalar(
        select(func.count())
        .select_from(NotificationLog)
        .where(
            NotificationLog.kind == "educator_onboarding_invite",
            NotificationLog.dedupe_key.like(f"educator_onboarding_invite:{form.id}:%"),
        )
    ) or 0
    link = form_link(form)
    subject, body = email_templates.render(
        db, "educator_onboarding_invite", full_name=user.full_name, link=link
    )
    sent = notify.send_once(
        db,
        to=user.email,
        subject=subject,
        body=body,
        booking_id=None,
        user_id=user.id,
        kind="educator_onboarding_invite",
        dedupe_key=f"educator_onboarding_invite:{form.id}:{prior_sends}",
    )
    if sent:
        form.sent_at = datetime.now(UTC)
        db.commit()
    return sent


def apply_submission(db: Session, form: EducatorOnboardingForm, data, *, source: str = "app") -> None:
    """Store a completed questionnaire. `data` is the validated Pydantic
    submit model; the whole payload is kept as the answers document and the
    signed declaration is copied to first-class columns."""
    payload = data.model_dump(mode="json")
    form.answers = payload
    form.signature_name = data.signature_name
    form.signed_date = data.signed_date
    form.status = "submitted"
    form.source = source
    form.submitted_at = datetime.now(UTC)
    db.commit()
