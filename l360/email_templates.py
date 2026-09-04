"""Editable templates for every email the system sends by itself.

Each automated email has a built-in default here — the exact wording that
was hard-coded at the call site before 04/09/2026 — and an admin can
override the subject or body from Admin → Email without a deploy. An
override is stored as two `app_settings` rows (`email_tpl.<kind>.subject`
and `.body`), so this needed no migration and no new table.

Placeholders are `{curly}` names listed per template. Substitution is
deliberately forgiving: an unknown or misspelt name is left on the page as
`{typo}` rather than raising, because a template edit must never be able to
stop an invoice or an invite from going out. Anything that renders is
plain text — these emails have never been HTML.

Call sites use `render(db, kind, **vars)`; a missing DB or a garbled
override falls back to the default, so email keeps working even if the
settings table is unreachable.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_SETTING_PREFIX = "email_tpl."
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

_SIGNOFF = "Warm regards,\nLearning 360° Foundation\nSwatar, Malta"


@dataclass(frozen=True)
class Template:
    kind: str
    label: str
    description: str
    subject: str
    body: str
    placeholders: tuple[tuple[str, str], ...]  # (name, what it fills in with)


def _t(kind, label, description, subject, body, placeholders) -> tuple[str, Template]:
    return kind, Template(kind, label, description, subject, body, tuple(placeholders))


DEFAULTS: dict[str, Template] = dict(
    [
        _t(
            "onboarding_invite",
            "Learner onboarding invite",
            "Sent to a parent or guardian when an admin invites them to fill in the client onboarding form.",
            "Welcome to Learning 360° — your onboarding form",
            "Dear {guardian_first_name} {guardian_surname},\n\n"
            "Welcome to Learning 360° Foundation.\n\n"
            "To complete your registration, please fill in our client onboarding "
            "form — it covers your contact details, your learner's details, and "
            "our policies, and takes about five minutes:\n\n"
            "{link}\n\n"
            "Your information is stored securely by Learning 360° Foundation and "
            "is never shared with third parties.\n\n"
            "If anything in the form is unclear, just reply to this email.\n\n"
            f"{_SIGNOFF}",
            [
                ("guardian_first_name", "the guardian's first name"),
                ("guardian_surname", "the guardian's surname"),
                ("link", "the personal link to their onboarding form"),
            ],
        ),
        _t(
            "onboarding_submitted",
            "Learner onboarding received",
            "The automatic thank-you a family gets the moment they submit their onboarding form.",
            "Learning 360° — onboarding form received",
            "Dear {guardian_first_name} {guardian_surname},\n\n"
            "Thank you — we've received your onboarding form for {learner_name}.\n"
            "We look forward to welcoming you to Learning 360° Foundation.\n\n"
            f"{_SIGNOFF}",
            [
                ("guardian_first_name", "the guardian's first name"),
                ("guardian_surname", "the guardian's surname"),
                ("learner_name", "the learner's name"),
            ],
        ),
        _t(
            "educator_onboarding_invite",
            "Educator onboarding invite",
            "Sent to a new educator when an admin invites them to complete their onboarding form.",
            "Welcome to Learning 360° — your educator onboarding form",
            "Dear {full_name},\n\n"
            "Welcome to the Learning 360° Foundation team!\n\n"
            "Before your first sessions we need a few things from you — your "
            "contact and right-to-work details, qualifications, availability, "
            "safeguarding declarations, referees and payment details. Our "
            "educator onboarding form collects all of it in one place and "
            "takes around 15–20 minutes. You can find it here:\n\n"
            "{link}\n\n"
            "Please have to hand: your ID/passport number, any teaching "
            "qualification details, two referees' contact details, and your "
            "bank details (IBAN) for payment.\n\n"
            "Everything you provide is handled confidentially and used only "
            "for recruitment, onboarding, safeguarding, scheduling, payment "
            "and legal compliance.\n\n"
            "If anything is unclear, just reply to this email.\n\n"
            f"{_SIGNOFF}",
            [
                ("full_name", "the educator's full name"),
                ("link", "the personal link to their onboarding form"),
            ],
        ),
        _t(
            "educator_onboarding_submitted",
            "Educator onboarding received",
            "The automatic thank-you an educator gets when they submit their onboarding form.",
            "Learning 360° — onboarding form received",
            "Dear {full_name},\n\n"
            "Thank you — we've received your educator onboarding form. We'll "
            "review it and complete the remaining checks, and be in touch about "
            "next steps.\n\n"
            f"{_SIGNOFF}",
            [("full_name", "the educator's full name")],
        ),
        _t(
            "confirmation",
            "Session booked",
            "Goes to the educator and the family as soon as a session is booked.",
            "Booking confirmed — {when}",
            "Session for {guardian_name} in {room_name}, {when} ({duration} minutes).\nStatus: {status}.",
            [
                ("when", "e.g. Monday 08 September 2026 at 14:30"),
                ("guardian_name", "the family's name"),
                ("room_name", "the room"),
                ("duration", "length in minutes"),
                ("status", "the session's status"),
            ],
        ),
        _t(
            "change",
            "Session moved",
            "Goes to the educator and the family when a booked session is moved.",
            "Booking changed — {when}",
            "Session for {guardian_name} in {room_name}, {when} ({duration} minutes).\nStatus: {status}.",
            [
                ("when", "the new date and time"),
                ("guardian_name", "the family's name"),
                ("room_name", "the room"),
                ("duration", "length in minutes"),
                ("status", "the session's status"),
            ],
        ),
        _t(
            "cancel",
            "Session cancelled",
            "Goes to the educator and the family when a session is cancelled.",
            "Booking cancelled — {when}",
            "Session for {guardian_name} in {room_name}, {when} ({duration} minutes).\nStatus: {status}.",
            [
                ("when", "the date and time it would have run"),
                ("guardian_name", "the family's name"),
                ("room_name", "the room"),
                ("duration", "length in minutes"),
                ("status", "the session's status"),
            ],
        ),
        _t(
            "reminder_24h",
            "Session reminder (24 hours before)",
            "Sent automatically to the educator and the family the day before a session.",
            "Reminder — session {when}",
            "Reminder: session with {guardian_name} {when}.",
            [
                ("when", "the date and time of the session"),
                ("guardian_name", "the family's name"),
            ],
        ),
        _t(
            "digest",
            "Educator daily digest",
            "Each morning, every educator with sessions that day gets one list of them.",
            "Your sessions today ({date})",
            "Today's sessions:\n{sessions}",
            [
                ("date", "today's date, e.g. 08 September"),
                ("sessions", "one line per session — time and family"),
                ("educator_name", "the educator's full name"),
            ],
        ),
        _t(
            "invoice_issued",
            "Invoice sent to a family",
            "The email a family receives with their invoice PDF attached. The PDF's own layout is set under Invoice template.",
            "Invoice {number} — €{total}",
            "Invoice {number} for the period {period_start} to {period_end} is attached.\n"
            "Total: €{total} (VAT exempt). Due: {due_date}.\n"
            'Please use "{number}" as your payment reference.',
            [
                ("number", "the invoice number"),
                ("total", "the amount due, e.g. 240.00"),
                ("period_start", "first day covered"),
                ("period_end", "last day covered"),
                ("due_date", "the payment due date"),
            ],
        ),
        _t(
            "password_reset",
            "Password reset",
            "Sent when a member of staff uses “Forgot password?”. The link expires in one hour and works once.",
            "Reset your Learning 360° password",
            "Hi {full_name},\n\n"
            "Click the link below to set a new password. It expires in 1 hour "
            "and can only be used once.\n\n{link}\n\n"
            "If you didn't request this, you can ignore this email.",
            [
                ("full_name", "the person's full name"),
                ("link", "the single-use reset link"),
            ],
        ),
    ]
)


def fill(text: str, values: dict[str, object]) -> str:
    """Replace {name} with values[name]. Unknown names are left visible so
    a typo in a template shows up as `{typo}` in the email instead of
    raising and blocking the send."""
    return _PLACEHOLDER_RE.sub(
        lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text
    )


def _overrides(db: Session | None, kind: str) -> dict[str, str]:
    if db is None:
        return {}
    try:
        from l360.models import AppSetting

        rows = db.scalars(
            select(AppSetting).where(
                AppSetting.key.in_([f"{_SETTING_PREFIX}{kind}.subject", f"{_SETTING_PREFIX}{kind}.body"])
            )
        ).all()
    except Exception:  # a template edit is never worth failing a send over
        logger.exception("Couldn't read email template overrides for %s", kind)
        return {}
    return {r.key.rsplit(".", 1)[1]: r.value for r in rows if r.value}


def get(db: Session | None, kind: str) -> tuple[str, str]:
    """The effective (subject, body) for a kind — the admin's override
    where one is saved, otherwise the built-in default."""
    default = DEFAULTS[kind]
    saved = _overrides(db, kind)
    return saved.get("subject") or default.subject, saved.get("body") or default.body


def render(db: Session | None, kind: str, **values) -> tuple[str, str]:
    """The (subject, body) to actually send, with placeholders filled."""
    subject, body = get(db, kind)
    return fill(subject, values), fill(body, values)


def setting_keys(kind: str) -> tuple[str, str]:
    return f"{_SETTING_PREFIX}{kind}.subject", f"{_SETTING_PREFIX}{kind}.body"
