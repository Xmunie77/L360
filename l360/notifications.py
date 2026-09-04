"""Booking-lifecycle email notifications (confirmation / change / cancel),
fired synchronously from the booking API routes. Idempotent per
booking+event+recipient via NotificationLog.dedupe_key, so a retried
request (or a race between two workers) never double-sends.
"""
from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import Session

from l360 import email_templates, notify
from l360.booking_logic import utc_to_local
from l360.models import Booking, Client, Room, User

EventKind = Literal["confirmation", "change", "cancel"]

def _describe(db: Session, booking: Booking) -> tuple[str, str, str]:
    room = db.get(Room, booking.room_id)
    client = db.get(Client, booking.client_id)
    local_date, local_time = utc_to_local(booking.start_utc)
    when = f"{local_date.strftime('%A %d %B %Y')} at {local_time.strftime('%H:%M')}"
    return when, room.name if room else "?", client.guardian_name if client else "?"


def notify_booking_event(db: Session, booking: Booking, kind: EventKind) -> None:
    when, room_name, guardian_name = _describe(db, booking)
    subject, body = email_templates.render(
        db,
        kind,
        when=when,
        room_name=room_name,
        guardian_name=guardian_name,
        duration=booking.duration_minutes,
        status=booking.status,
    )
    # Dedupe key includes the booking's current start/status so a
    # "confirmation" then later a "change" to the same booking are both
    # sent — only an exact retry of the same event is suppressed.
    dedupe_base = f"{kind}:{booking.id}:{booking.start_utc.isoformat()}:{booking.status}"

    educator = db.get(User, booking.educator_id)
    client = db.get(Client, booking.client_id)
    recipients: list[tuple[str, int | None]] = []
    if educator and educator.email:
        recipients.append((educator.email, educator.id))
    if client and client.email:
        recipients.append((client.email, None))

    for email, user_id in recipients:
        notify.send_once(
            db,
            to=email,
            subject=subject,
            body=body,
            booking_id=booking.id,
            user_id=user_id,
            kind=kind,
            dedupe_key=f"{dedupe_base}:{email}",
        )
