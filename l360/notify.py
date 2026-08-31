"""Email transport — SMTP if configured, otherwise logs to console.

The console fallback is a deliberate, safe default for local dev and for
any environment where SMTP_HOST hasn't been set yet: notifications degrade
to visible log lines instead of silently failing or crashing the request.
"""
from __future__ import annotations

import hashlib
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from l360.config import EMAIL_FROM, SESSION_SECRET, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER
from l360.models import AppSetting, NotificationLog

logger = logging.getLogger("l360.notify")

# --- at-rest encryption for the stored SMTP password (P1-4) -----------------
# Fernet keyed off L360_SESSION_SECRET: the DB row alone is useless without
# the app's secret. Values are prefixed "enc:"; a legacy plaintext row (saved
# before 31/08/2026) still reads correctly and is re-encrypted on next save.
_ENC_PREFIX = "enc:"


def _fernet():
    import base64

    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(hashlib.sha256(("smtp:" + SESSION_SECRET).encode()).digest())
    return Fernet(key)


def encrypt_setting(value: str) -> str:
    return _ENC_PREFIX + _fernet().encrypt(value.encode()).decode()


def decrypt_setting(value: str) -> str:
    if not value.startswith(_ENC_PREFIX):
        return value  # legacy plaintext
    try:
        return _fernet().decrypt(value[len(_ENC_PREFIX):].encode()).decode()
    except Exception:
        logger.error("Stored SMTP password failed to decrypt — was L360_SESSION_SECRET rotated? Re-save it in Admin → Email.")
        return ""

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
        cfg["password"] = decrypt_setting(rows["smtp_password"])
    if rows.get("smtp_from"):
        cfg["from"] = rows["smtp_from"]
    return cfg


def send_email(to: str, subject: str, body: str, attachment: tuple[str, bytes] | None = None) -> None:
    """attachment: optional (filename, pdf_bytes) — currently always a PDF."""
    cfg = smtp_config()
    if not cfg["host"]:
        logger.info("EMAIL (SMTP not configured) to=%s subject=%r attachment=%s\n%s",
                    to, subject, attachment[0] if attachment else None, body)
        return
    msg = EmailMessage()
    msg["From"] = cfg["from"] or cfg["user"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if attachment:
        filename, payload = attachment
        msg.add_attachment(payload, maintype="application", subtype="pdf", filename=filename)
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
    attachment: tuple[str, bytes] | None = None,
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
        send_email(to, subject, body, attachment=attachment)
    except (smtplib.SMTPException, OSError):
        logger.exception("EMAIL FAILED to=%s kind=%s dedupe_key=%s", to, kind, dedupe_key)
        db.rollback()
        return False
    db.commit()
    return True
