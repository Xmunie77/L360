"""Token-authenticated public surfaces: the iCal feed.

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

from l360.deps import _client_label, _upsert_setting, require_admin, require_user  # noqa: F401

router = APIRouter()


# --- iCal feed -----------------------------------------------------------
@router.get("/api/me/calendar-token", response_model=CalendarTokenOut | None)
def get_my_calendar_token(db: Session = Depends(get_session), user: User = Depends(require_user)):
    row = db.scalar(select(CalendarToken).where(CalendarToken.user_id == user.id, CalendarToken.revoked_at.is_(None)))
    if row is None:
        return None
    return CalendarTokenOut(token=row.token, feed_path=f"/api/calendar/{row.token}.ics")


@router.post("/api/me/calendar-token", response_model=CalendarTokenOut)
def create_or_rotate_calendar_token(db: Session = Depends(get_session), user: User = Depends(require_user)):
    existing = db.scalar(select(CalendarToken).where(CalendarToken.user_id == user.id))
    new_token = secrets.token_urlsafe(32)
    if existing is None:
        row = CalendarToken(user_id=user.id, token=new_token)
        db.add(row)
    else:
        existing.token = new_token
        existing.revoked_at = None
        row = existing
    db.commit()
    db.refresh(row)
    return CalendarTokenOut(token=row.token, feed_path=f"/api/calendar/{row.token}.ics")


@router.delete("/api/me/calendar-token")
def revoke_calendar_token(db: Session = Depends(get_session), user: User = Depends(require_user)):
    row = db.scalar(select(CalendarToken).where(CalendarToken.user_id == user.id))
    if row is not None:
        row.revoked_at = datetime.now(UTC)
        db.commit()
    return {"ok": True}


@router.get("/api/calendar/{token}.ics")
def calendar_feed(token: str, db: Session = Depends(get_session)):
    # Deliberately NOT behind require_user — calendar apps subscribe by URL,
    # they can't do cookie/session login. The token itself is the auth; a
    # leaked URL is revoked via DELETE /api/me/calendar-token, not a
    # password change.
    row = db.scalar(select(CalendarToken).where(CalendarToken.token == token, CalendarToken.revoked_at.is_(None)))
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown or revoked calendar link")
    bookings = db.scalars(select(Booking).where(Booking.educator_id == row.user_id)).all()
    rooms = {r.id: r for r in db.scalars(select(Room))}
    clients = {c.id: c for c in db.scalars(select(Client).where(Client.id.in_({b.client_id for b in bookings})))} if bookings else {}
    events = []
    for b in bookings:
        room = rooms.get(b.room_id)
        client = clients.get(b.client_id)
        events.append((b, room.name if room else "?", _client_label(client) if client else "?"))
    return PlainTextResponse(ical.render_ics(events), media_type="text/calendar")

@router.get("/privacy")
def privacy_notice():
    """Public privacy notice (draft pending legal review) — linked from the
    footers of both public onboarding forms."""
    from fastapi.responses import HTMLResponse

    from l360.privacy import PRIVACY_HTML

    return HTMLResponse(PRIVACY_HTML)
