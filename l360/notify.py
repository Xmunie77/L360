"""Email transport — SMTP if configured, otherwise logs to console.

The console fallback is a deliberate, safe default for local dev and for
any environment where SMTP_HOST hasn't been set yet: notifications degrade
to visible log lines instead of silently failing or crashing the request.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from l360.config import EMAIL_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER
from l360.models import NotificationLog

logger = logging.getLogger("l360.notify")


def send_email(to: str, subject: str, body: str) -> None:
    if not SMTP_HOST:
        logger.info("EMAIL (SMTP not configured) to=%s subject=%r\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM or SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def send_once(
    db: Session,
    *,
    to: str,
    subject: str,
    body: str,
    booking_id: int | None,
    user_id: int | None,
    kind: str,
    dedupe_key: str,
) -> bool:
    """Send exactly once per dedupe_key, ever. Logs the send first and
    relies on NotificationLog's unique constraint: a retried request or a
    concurrent duplicate just hits IntegrityError and is treated as
    "already sent" rather than sending twice. Returns whether it sent."""
    db.add(NotificationLog(booking_id=booking_id, user_id=user_id, kind=kind, dedupe_key=dedupe_key))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    send_email(to, subject, body)
    db.commit()
    return True
