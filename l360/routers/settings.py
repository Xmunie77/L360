"""Admin email (SMTP) settings + test send.

Split out of the monolithic api.py on 31/08/2026 (P3 of the engineering
review) — routes are verbatim; only the decorator target changed.
"""

from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from datetime import date as date_cls
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError as _IntegrityError
from sqlalchemy.orm import Session

from l360 import auth, billing_logic, booking_logic, contract, educator_onboarding, email_templates, ical, invoice_pdf, notifications, notify, onboarding, reconciliation, statements_logic
from l360.billing_logic import BillingError
from l360.booking_logic import SlotError
from l360.config import (
    CANCELLATION_CUTOFF_HOURS,
    COOKIE_SECURE,
    IS_POSTGRES,
    PUBLIC_BASE_URL,
    SESSION_COOKIE_NAME,
    assert_secure_config,
)
from l360.db import get_session, init_db
from l360.models import (
    BankTxn,
    Booking,
    BookingSeries,
    CalendarToken,
    Client,
    EducatorLevel,
    FacilityClosure,
    FacilityHours,
    Invoice,
    InvoiceLine,
    AppSetting,
    EducatorOnboardingForm,
    OnboardingForm,
    PasswordResetToken,
    PriceListEntry,
    Room,
    ServiceType,
    User,
)
from l360.payments.provider import ProviderNotConfigured
from l360.schemas import (
    BankTxnOut,
    BillingRunIn,
    BillingRunOut,
    BookingIn,
    BookingMoveIn,
    BookingOut,
    BookingSeriesIn,
    BookingSeriesOut,
    BookingStatusIn,
    CalendarTokenOut,
    ChangePasswordIn,
    ClientBrief,
    ClientIn,
    ClientOut,
    ClientStatementOut,
    EducatorLevelIn,
    EducatorLevelOut,
    EducatorSummaryOut,
    FacilityClosureIn,
    FacilityClosureOut,
    FacilityHoursIn,
    FacilityHoursOut,
    ForgotPasswordIn,
    InvoiceDetailOut,
    InvoiceLineOut,
    InvoiceOut,
    LoginReq,
    ManualMatchIn,
    MeResp,
    NextAvailableOut,
    EducatorChecklistIn,
    EducatorOnboardingAdminOut,
    EducatorOnboardingPrefillOut,
    EducatorOnboardingSubmitIn,
    EmailSettingsIn,
    EmailTemplateIn,
    EmailTemplateOut,
    EmailSettingsOut,
    EmailTestOut,
    InvoiceSettingsIn,
    InvoiceSettingsOut,
    OnboardingAdminOut,
    OnboardingPrefillOut,
    OnboardingSubmitIn,
    PaymentOut,
    PriceListEntryIn,
    PriceListEntryOut,
    RecordPaymentIn,
    ResetPasswordIn,
    RoomIn,
    RoomOut,
    RoomUtilisationOut,
    ServiceTypeIn,
    ServiceTypeOut,
    SkippedOccurrence,
    StatementInvoiceLineOut,
    StatementPaymentLineOut,
    SummarySessionLineOut,
    SyncResultOut,
    UserIn,
    UserOut,
    UserUpdate,
)

from l360.deps import _client_label, _upsert_setting, require_admin, require_user  # noqa: F401

router = APIRouter()


# --- admin: email (SMTP) settings ------------------------------------------
# Editable in-app so the founders configure sending without Fly secrets.
# The password is write-only: saved when provided, kept when blank, and
# never returned by the API. Env vars remain the fallback for any field
# left blank here (see notify.smtp_config).

def _upsert_setting(db: Session, key: str, value: str) -> None:
    row = db.scalar(select(AppSetting).where(AppSetting.key == key))
    if value:
        if row is None:
            db.add(AppSetting(key=key, value=value))
        else:
            row.value = value
    elif row is not None:
        db.delete(row)


@router.get("/api/admin/email-settings", response_model=EmailSettingsOut)
def admin_get_email_settings(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    cfg = notify.smtp_config()
    return EmailSettingsOut(
        host=cfg["host"], port=cfg["port"], user=cfg["user"], email_from=cfg["from"],
        password_set=bool(cfg["password"]),
    )


@router.put("/api/admin/email-settings", response_model=EmailSettingsOut)
def admin_save_email_settings(
    body: EmailSettingsIn, db: Session = Depends(get_session), admin: User = Depends(require_admin)
):
    _upsert_setting(db, "smtp_host", body.host.strip())
    _upsert_setting(db, "smtp_port", str(body.port))
    _upsert_setting(db, "smtp_user", body.user.strip())
    _upsert_setting(db, "smtp_from", body.email_from.strip())
    if body.password:  # blank = keep the stored password
        _upsert_setting(db, "smtp_password", notify.encrypt_setting(body.password))
    db.commit()
    return admin_get_email_settings(db, admin)


@router.post("/api/admin/email-settings/test", response_model=EmailTestOut)
def admin_test_email(db: Session = Depends(get_session), admin: User = Depends(require_admin)):
    """Send a test email to the signed-in admin so a wrong app password
    shows up immediately, not on the first real invite."""
    cfg = notify.smtp_config()
    if not cfg["host"]:
        return EmailTestOut(ok=False, detail="No SMTP host configured — emails currently only log to the server console.")
    try:
        notify.send_email(
            admin.email,
            "Learning 360\u00b0 — test email",
            "This is a test email from the Learning 360\u00b0 OS. If you can read this, email sending is working.",
        )
    except Exception as e:  # surface the SMTP error verbatim to the admin
        return EmailTestOut(ok=False, detail=f"Send failed: {e}")
    return EmailTestOut(ok=True, detail=f"Test email sent to {admin.email}.")

def _template_out(db: Session, kind: str) -> EmailTemplateOut:
    tpl = email_templates.DEFAULTS[kind]
    subject, body = email_templates.get(db, kind)
    return EmailTemplateOut(
        kind=kind,
        label=tpl.label,
        description=tpl.description,
        subject=subject,
        body=body,
        default_subject=tpl.subject,
        default_body=tpl.body,
        is_custom=subject != tpl.subject or body != tpl.body,
        placeholders=list(tpl.placeholders),
    )


@router.get("/api/admin/email-templates", response_model=list[EmailTemplateOut])
def admin_list_email_templates(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return [_template_out(db, kind) for kind in email_templates.DEFAULTS]


@router.put("/api/admin/email-templates/{kind}", response_model=EmailTemplateOut)
def admin_save_email_template(
    kind: str, body: EmailTemplateIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    tpl = email_templates.DEFAULTS.get(kind)
    if tpl is None:
        raise HTTPException(status_code=404, detail="No such email template.")
    subject = body.subject.strip()
    text = body.body.strip()
    if not subject or not text:
        raise HTTPException(status_code=422, detail="Subject and body can't be empty — use Reset to go back to the default wording.")
    subject_key, body_key = email_templates.setting_keys(kind)
    # Saving wording identical to the default clears the override, so
    # "is_custom" always means a real difference.
    _upsert_setting(db, subject_key, "" if subject == tpl.subject else subject)
    _upsert_setting(db, body_key, "" if text == tpl.body else text)
    db.commit()
    return _template_out(db, kind)


@router.delete("/api/admin/email-templates/{kind}", response_model=EmailTemplateOut)
def admin_reset_email_template(kind: str, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    if kind not in email_templates.DEFAULTS:
        raise HTTPException(status_code=404, detail="No such email template.")
    subject_key, body_key = email_templates.setting_keys(kind)
    _upsert_setting(db, subject_key, "")
    _upsert_setting(db, body_key, "")
    db.commit()
    return _template_out(db, kind)
