"""Bookings: create/move/cancel/status, series, next-available.

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


# --- bookings ------------------------------------------------------------
def _client_label(client: Client) -> str:
    name = f"{client.guardian_first_name} {client.guardian_surname}"
    return f"{name} ({client.child_name})" if client.child_name else name


def _booking_outs(db: Session, bookings: list[Booking]) -> list[BookingOut]:
    """Batch shape conversion — one query per entity type for the whole
    list, instead of three db.get() calls per booking (P2, 31/08 review)."""
    if not bookings:
        return []
    rooms = {r.id: r for r in db.scalars(select(Room).where(Room.id.in_({b.room_id for b in bookings})))}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({b.educator_id for b in bookings})))}
    clients = {c.id: c for c in db.scalars(select(Client).where(Client.id.in_({b.client_id for b in bookings})))}
    st_ids = {b.service_type_id for b in bookings if b.service_type_id}
    service_types = {t.id: t for t in db.scalars(select(ServiceType).where(ServiceType.id.in_(st_ids)))} if st_ids else {}
    out = []
    for b in bookings:
        room = rooms.get(b.room_id)
        educator = users.get(b.educator_id)
        client = clients.get(b.client_id)
        service_type = service_types.get(b.service_type_id) if b.service_type_id else None
        out.append(BookingOut(
            id=b.id,
            room_id=b.room_id,
            room_name=room.name if room else "?",
            educator_id=b.educator_id,
            educator_name=educator.full_name if educator else "?",
            client_id=b.client_id,
            client_label=_client_label(client) if client else "?",
            service_type_id=b.service_type_id,
            service_type_name=service_type.name if service_type else None,
            client_price_cents=b.client_price_cents,
            tutor_payment_cents=b.tutor_payment_cents,
            series_id=b.series_id,
            start_utc=b.start_utc,
            duration_minutes=b.duration_minutes,
            status=b.status,
            notes=b.notes,
            created_by=b.created_by,
            created_at=b.created_at,
            cancelled_at=b.cancelled_at,
        ))
    return out


def _booking_out(db: Session, b: Booking) -> BookingOut:
    room = db.get(Room, b.room_id)
    educator = db.get(User, b.educator_id)
    client = db.get(Client, b.client_id)
    service_type = db.get(ServiceType, b.service_type_id) if b.service_type_id else None
    return BookingOut(
        id=b.id,
        room_id=b.room_id,
        room_name=room.name if room else "?",
        educator_id=b.educator_id,
        educator_name=educator.full_name if educator else "?",
        client_id=b.client_id,
        client_label=_client_label(client) if client else "?",
        series_id=b.series_id,
        service_type_id=b.service_type_id,
        service_type_name=service_type.name if service_type else None,
        client_price_cents=b.client_price_cents,
        tutor_payment_cents=b.tutor_payment_cents,
        start_utc=b.start_utc,
        duration_minutes=b.duration_minutes,
        status=b.status,
        notes=b.notes,
        created_by=b.created_by,
        created_at=b.created_at,
        cancelled_at=b.cancelled_at,
    )



def _commit_booking_write(db: Session) -> None:
    """Commit a booking insert/move, translating the Postgres exclusion
    constraints (excl_booking_*_overlap, migration 0017) into the same 409
    the slot validator raises — they only fire when two requests raced past
    validate_slot() simultaneously."""
    try:
        db.commit()
    except _IntegrityError as e:
        db.rollback()
        if "excl_booking" in str(e.orig):
            raise HTTPException(status_code=409, detail="That slot was just taken by another booking")
        raise


def _can_modify(user: User, booking: Booking) -> bool:
    return user.role == "admin" or booking.educator_id == user.id or booking.created_by == user.id


@router.get("/api/bookings", response_model=list[BookingOut])
def list_bookings(
    start: datetime,
    end: datetime,
    room_id: int | None = None,
    educator_id: int | None = None,
    mine: bool = False,
    db: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    q = select(Booking).where(Booking.start_utc >= start, Booking.start_utc < end)
    if room_id is not None:
        q = q.where(Booking.room_id == room_id)
    if educator_id is not None:
        q = q.where(Booking.educator_id == educator_id)
    if mine:
        q = q.where(Booking.educator_id == user.id)
    rows = db.scalars(q.order_by(Booking.start_utc)).all()
    return _booking_outs(db, list(rows))


@router.get("/api/bookings/next-available", response_model=NextAvailableOut)
def next_available_room(
    duration_minutes: int = 60, db: Session = Depends(get_session), _user: User = Depends(require_user)
):
    # A bare `Literal[60, 90, 120]` query param doesn't coerce a raw query
    # string ("60") the way a JSON body does, so validate it by hand here
    # rather than relying on FastAPI/Pydantic to reject a plain int.
    if duration_minutes not in (60, 90, 120):
        raise HTTPException(status_code=422, detail="duration_minutes must be 60, 90, or 120")
    found = booking_logic.find_next_available_room(db, duration_minutes=duration_minutes)
    if found is None:
        reason = "no_facility_hours" if not booking_logic.facility_hours_configured(db) else "fully_booked"
        return NextAvailableOut(reason=reason)
    room, start_utc = found
    return NextAvailableOut(room_id=room.id, room_name=room.name, start_utc=start_utc)


@router.get("/api/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, db: Session = Depends(get_session), _user: User = Depends(require_user)):
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _booking_out(db, b)


def _resolve_bookable_service_type(db: Session, service_type_id: int) -> ServiceType:
    """A booking must reference an active "session" item from the L360
    price list — "additional_service" items (flashcards, etc.) aren't
    calendar bookings, so they're not valid here."""
    service_type = db.get(ServiceType, service_type_id)
    if service_type is None or not service_type.active or service_type.category != "session":
        raise HTTPException(status_code=422, detail="Not a valid bookable session type")
    return service_type


@router.post("/api/bookings", response_model=BookingOut)
def create_booking(body: BookingIn, db: Session = Depends(get_session), user: User = Depends(require_user)):
    service_type = _resolve_bookable_service_type(db, body.service_type_id)
    try:
        booking_logic.validate_slot(
            db,
            room_id=body.room_id,
            educator_id=body.educator_id,
            start_utc=body.start_utc,
            duration_minutes=body.duration_minutes,
        )
    except SlotError as e:
        raise HTTPException(status_code=409, detail=e.reason)

    row = Booking(
        room_id=body.room_id,
        educator_id=body.educator_id,
        client_id=body.client_id,
        service_type_id=body.service_type_id,
        # Locked in now — a later edit to the service type's price must
        # never change what this booking bills at.
        client_price_cents=service_type.client_price_cents,
        tutor_payment_cents=service_type.tutor_payment_cents,
        start_utc=body.start_utc,
        duration_minutes=body.duration_minutes,
        notes=body.notes,
        created_by=user.id,
    )
    db.add(row)
    _commit_booking_write(db)
    db.refresh(row)
    notifications.notify_booking_event(db, row, "confirmation")
    return _booking_out(db, row)


@router.post("/api/bookings/series", response_model=BookingSeriesOut)
def create_booking_series(
    body: BookingSeriesIn, db: Session = Depends(get_session), user: User = Depends(require_user)
):
    service_type = _resolve_bookable_service_type(db, body.service_type_id)
    dates = booking_logic.expand_weekly_dates(body.starts_on, body.ends_on, body.weekday, body.interval_weeks)
    if not dates:
        raise HTTPException(status_code=422, detail="No occurrences between starts_on and ends_on")

    series = BookingSeries(
        room_id=body.room_id,
        educator_id=body.educator_id,
        client_id=body.client_id,
        service_type_id=body.service_type_id,
        weekday=body.weekday,
        local_time=body.local_time,
        duration_minutes=body.duration_minutes,
        starts_on=body.starts_on,
        ends_on=body.ends_on,
        interval_weeks=body.interval_weeks,
    )
    db.add(series)
    db.flush()  # assign series.id without committing yet

    created: list[Booking] = []
    skipped: list[SkippedOccurrence] = []
    for occ_date in dates:
        start_utc = booking_logic.local_to_utc(occ_date, body.local_time)
        try:
            booking_logic.validate_slot(
                db,
                room_id=body.room_id,
                educator_id=body.educator_id,
                start_utc=start_utc,
                duration_minutes=body.duration_minutes,
            )
        except SlotError as e:
            skipped.append(SkippedOccurrence(date=occ_date, reason=e.reason))
            continue
        row = Booking(
            room_id=body.room_id,
            educator_id=body.educator_id,
            client_id=body.client_id,
            series_id=series.id,
            service_type_id=body.service_type_id,
            client_price_cents=service_type.client_price_cents,
            tutor_payment_cents=service_type.tutor_payment_cents,
            start_utc=start_utc,
            duration_minutes=body.duration_minutes,
            notes=body.notes,
            created_by=user.id,
        )
        db.add(row)
        try:
            db.flush()
        except _IntegrityError as e:
            # A concurrent booking raced us onto this occurrence between
            # validate_slot and the flush (exclusion constraint, mig 0017).
            db.rollback()
            if "excl_booking" not in str(e.orig):
                raise
            raise HTTPException(status_code=409, detail="A slot in this series was just taken by another booking — please retry")
        created.append(row)

    _commit_booking_write(db)
    for b in created:
        notifications.notify_booking_event(db, b, "confirmation")
    return BookingSeriesOut(
        series_id=series.id,
        created=_booking_outs(db, created),
        skipped=skipped,
    )


@router.patch("/api/bookings/{booking_id}", response_model=BookingOut)
def move_booking(
    booking_id: int,
    body: BookingMoveIn,
    db: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Not found")
    if not _can_modify(user, b):
        raise HTTPException(status_code=403, detail="Not your booking")
    if b.status != "confirmed":
        raise HTTPException(status_code=409, detail=f"Cannot move a {b.status} booking")

    new_service_type = _resolve_bookable_service_type(db, body.service_type_id) if body.service_type_id is not None else None

    new_room_id = body.room_id if body.room_id is not None else b.room_id
    new_start = body.start_utc if body.start_utc is not None else b.start_utc
    new_duration = body.duration_minutes if body.duration_minutes is not None else b.duration_minutes

    try:
        booking_logic.validate_slot(
            db,
            room_id=new_room_id,
            educator_id=b.educator_id,
            start_utc=new_start,
            duration_minutes=new_duration,
            exclude_booking_id=b.id,
        )
    except SlotError as e:
        raise HTTPException(status_code=409, detail=e.reason)

    b.room_id = new_room_id
    b.start_utc = new_start
    b.duration_minutes = new_duration
    if new_service_type is not None:
        b.service_type_id = new_service_type.id
        # Re-locked to the new service type's current price — this is a
        # deliberate change of what's being billed, not a price-list edit.
        b.client_price_cents = new_service_type.client_price_cents
        b.tutor_payment_cents = new_service_type.tutor_payment_cents
    if body.notes is not None:
        b.notes = body.notes
    _commit_booking_write(db)
    db.refresh(b)
    notifications.notify_booking_event(db, b, "change")
    return _booking_out(db, b)


@router.post("/api/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: int, db: Session = Depends(get_session), user: User = Depends(require_user)):
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Not found")
    if not _can_modify(user, b):
        raise HTTPException(status_code=403, detail="Not your booking")
    if b.status != "confirmed":
        raise HTTPException(status_code=409, detail=f"Already {b.status}")

    now = datetime.now(UTC)
    cutoff = timedelta(hours=CANCELLATION_CUTOFF_HOURS)
    # Inside the cutoff window: still billable ("late"). Outside it: free.
    b.status = "cancelled_late" if (b.start_utc - now) < cutoff else "cancelled"
    b.cancelled_at = now
    db.commit()
    db.refresh(b)
    notifications.notify_booking_event(db, b, "cancel")
    return _booking_out(db, b)


@router.post("/api/bookings/{booking_id}/status", response_model=BookingOut)
def set_booking_status(
    booking_id: int,
    body: BookingStatusIn,
    db: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    """Admin marks a past confirmed booking as completed or no-show —
    feeds the billing run in a later phase."""
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Not found")
    if b.status != "confirmed":
        raise HTTPException(status_code=409, detail=f"Already {b.status}")
    if b.start_utc > datetime.now(UTC):
        raise HTTPException(status_code=409, detail="Booking hasn't happened yet")
    b.status = body.status
    db.commit()
    db.refresh(b)
    return _booking_out(db, b)


