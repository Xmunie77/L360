"""Email transport — SMTP if configured, otherwise logs to console.

The console fallback is a deliberate, safe default for local dev and for
any environment where SMTP_HOST hasn't been set yet: notifications degrade
to visible log lines instead of silently failing or crashing the request.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from l360.config import EMAIL_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER
from l360.models import AppSetting, NotificationLog

logger = logging.getLogger("l360.notify")

# app_settings keys for email config, editable from Admin → Email. A DB
# value overrides the corresponding env var; env vars stay as a fallback so
# a Fly-secrets setup keeps working untouched.
SMTP_SETTING_KEYS = ("smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_from")


def smtp_config() -> dict:
    """Effective SMTP config: env-var base, overridden per-field by any
    app_settings rows. Never raises — a DB hiccup just means env config."""
    cfg = {
        "host": SMTP_HOST,
        "port": SMTP_PORT,
        "user": SMTP_USER,
        "password": SMTP_PASSWORD,
        "from": EMAIL_FROM,
    }
    try:
        from l360.db import SessionLocal

        with SessionLocal() as s:
            rows = {
                r.key: r.value
                for r in s.scalars(select(AppSetting).where(AppSetting.key.in_(SMTP_SETTING_KEYS)))
            }
    except Exception:
        return cfg
    if rows.get("smtp_host"):
        cfg["host"] = rows["smtp_host"]
    if rows.get("smtp_port"):
        try:
            cfg["port"] = int(rows["smtp_port"])
        except ValueError:
            pass
    if rows.get("smtp_user"):
        cfg["user"] = rows["smtp_user"]
    if rows.get("smtp_password"):
        cfg["password"] = rows["smtp_password"]
    if rows.get("smtp_from"):
        cfg["from"] = rows["smtp_from"]
    return cfg


def send_email(to: str, subject: str, body: str) -> None:
    cfg = smtp_config()
    if not cfg["host"]:
        logger.info("EMAIL (SMTP not configured) to=%s subject=%r\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"] = cfg["from"] or cfg["user"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
        server.starttls()
        if cfg["user"]:
            server.login(cfg["user"], cfg["password"])
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
    "already sent" rather than sending twice. Returns whether it sent.

    An SMTP failure (host down, bad credentials, rejected recipient) must
    never fail the request that triggered the notification — the booking or
    learner write has already happened. Roll back the dedupe row so a later
    retry can actually send, log the error, and report "not sent"."""
    db.add(NotificationLog(booking_id=booking_id, user_id=user_id, kind=kind, dedupe_key=dedupe_key))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    try:
        send_email(to, subject, body)
    except (smtplib.SMTPException, OSError):
        logger.exception("EMAIL FAILED to=%s kind=%s dedupe_key=%s", to, kind, dedupe_key)
        db.rollback()
        return False
    db.commit()
    return True
