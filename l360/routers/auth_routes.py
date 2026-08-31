"""Auth: login/logout/session, password reset + change, /api/me.

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

from l360 import auth, billing_logic, booking_logic, contract, educator_onboarding, ical, invoice_pdf, notifications, notify, onboarding, reconciliation, statements_logic
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

from l360.deps import _client_label, _current_user, _upsert_setting, require_admin, require_user  # noqa: F401

router = APIRouter()


_LOCKOUT_THRESHOLD = 5
_LOCKOUT_MINUTES = 15


@router.post("/api/login")
def login(body: LoginReq, response: Response, db: Session = Depends(get_session)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    now = datetime.now(UTC)
    if user is not None and user.locked_until is not None and user.locked_until > now:
        # 401, same message as a wrong password — a different status/message
        # would leak which accounts exist and when they unlock.
        raise HTTPException(status_code=401, detail="Wrong email or password")
    if user is None or not user.active or not auth.verify_password(body.password, user.password_hash):
        if user is not None and user.active:
            user.failed_logins += 1
            if user.failed_logins >= _LOCKOUT_THRESHOLD:
                user.locked_until = now + timedelta(minutes=_LOCKOUT_MINUTES)
                user.failed_logins = 0
            db.commit()
        raise HTTPException(status_code=401, detail="Wrong email or password")
    if user.failed_logins or user.locked_until:
        user.failed_logins = 0
        user.locked_until = None
        db.commit()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        auth.issue_session_cookie(user.id, user.role, user.password_hash),
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        max_age=60 * 60 * 24 * 14,
    )
    return {"ok": True}


@router.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}


@router.get("/api/session")
def session(l360_session: str | None = Cookie(default=None), db: Session = Depends(get_session)):
    user = _current_user(db, l360_session)
    return {"authed": user is not None}


_RESET_TOKEN_TTL = timedelta(hours=1)


@router.post("/api/forgot-password")
def forgot_password(body: ForgotPasswordIn, db: Session = Depends(get_session)):
    # Always returns {"ok": True} whether or not the email is registered —
    # revealing that would let an attacker enumerate real accounts.
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is not None and user.active:
        # At most one live token per user: superseding a request invalidates
        # any earlier unused link rather than leaving multiple valid ones.
        db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=datetime.now(UTC))
        )
        token = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(
            user_id=user.id, token=token, expires_at=datetime.now(UTC) + _RESET_TOKEN_TTL,
        ))
        db.commit()
        link = f"{PUBLIC_BASE_URL}/?reset={token}"
        notify.send_email(
            user.email,
            "Reset your Learning 360° password",
            f"Hi {user.full_name},\n\n"
            f"Click the link below to set a new password. It expires in 1 hour "
            f"and can only be used once.\n\n{link}\n\n"
            "If you didn't request this, you can ignore this email.",
        )
    return {"ok": True}


@router.post("/api/reset-password")
def reset_password(body: ResetPasswordIn, db: Session = Depends(get_session)):
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token == body.token))
    if (
        row is None
        or row.used_at is not None
        or row.expires_at < datetime.now(UTC)
    ):
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
    user = db.get(User, row.user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
    user.password_hash = auth.hash_password(body.password)
    row.used_at = datetime.now(UTC)
    db.commit()
    return {"ok": True}


@router.get("/api/me", response_model=MeResp)
def me(user: User = Depends(require_user)):
    return user


@router.post("/api/me/password")
def change_my_password(body: ChangePasswordIn, db: Session = Depends(get_session), user: User = Depends(require_user)):
    """Self-service password change from the Profile page — requires the
    current password, unlike the admin reset in /api/admin/users."""
    if not auth.verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=403, detail="Current password is wrong.")
    user.password_hash = auth.hash_password(body.new_password)
    db.commit()
    return {"ok": True}


