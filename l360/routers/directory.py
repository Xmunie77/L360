"""Directory + admin config: rooms, levels, users, service types, price list, hours, closures.

Split out of the monolithic api.py on 31/08/2026 (P3 of the engineering
review) — routes are verbatim; only the decorator target changed.
"""

from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from datetime import date as date_cls
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, File, HTTPException, Response, UploadFile
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
    ProfileUpdateIn,
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


# --- read-only lists for any authed user ------------------------------
@router.get("/api/rooms", response_model=list[RoomOut])
def list_rooms_ro(db: Session = Depends(get_session), _user: User = Depends(require_user)):
    return db.scalars(select(Room).where(Room.active == True).order_by(Room.name)).all()  # noqa: E712


@router.get("/api/educators", response_model=list[UserOut])
def list_educators_ro(db: Session = Depends(get_session), _user: User = Depends(require_user)):
    # Anyone with a level assigned delivers sessions and is bookable — not
    # just role="educator". An admin who's also a founder/educator shows up
    # here too once they're given a level.
    return db.scalars(
        select(User).where(User.level_id.is_not(None), User.active == True).order_by(User.full_name)  # noqa: E712
    ).all()


@router.get("/api/session-types", response_model=list[ServiceTypeOut])
def list_session_types_ro(db: Session = Depends(get_session), _user: User = Depends(require_user)):
    # Only bookable "session" items — "additional_service" ones (flashcards,
    # etc.) aren't calendar bookings, so they're never offered here.
    return db.scalars(
        select(ServiceType)
        .where(ServiceType.category == "session", ServiceType.active == True)  # noqa: E712
        .order_by(ServiceType.sort_order, ServiceType.name)
    ).all()


@router.get("/api/clients", response_model=list[ClientBrief])
def list_clients_ro(db: Session = Depends(get_session), _user: User = Depends(require_user)):
    return db.scalars(
        select(Client).where(Client.active == True).order_by(Client.guardian_surname, Client.guardian_first_name)
    ).all()  # noqa: E712


@router.get("/api/price-list/current", response_model=list[PriceListEntryOut])
def price_list_current(
    as_of: date_cls | None = None,
    db: Session = Depends(get_session),
    _user: User = Depends(require_user),
):
    """For each (level, duration), the entry with the latest valid_from <= as_of."""
    # Malta calendar date, not the UTC server date — a price change taking
    # effect "today" must apply from Malta midnight, not 2am.
    as_of = as_of or booking_logic.local_today()
    rows = db.scalars(select(PriceListEntry).where(PriceListEntry.valid_from <= as_of)).all()
    latest: dict[tuple[int, int], PriceListEntry] = {}
    for row in rows:
        key = (row.level_id, row.duration_minutes)
        if key not in latest or row.valid_from > latest[key].valid_from:
            latest[key] = row
    return list(latest.values())



# --- admin: educator levels ----------------------------------------------
@router.get("/api/admin/educator-levels", response_model=list[EducatorLevelOut])
def admin_list_levels(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(select(EducatorLevel).order_by(EducatorLevel.sort_order)).all()


@router.post("/api/admin/educator-levels", response_model=EducatorLevelOut)
def admin_create_level(
    body: EducatorLevelIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = EducatorLevel(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/api/admin/educator-levels/{level_id}", response_model=EducatorLevelOut)
def admin_update_level(
    level_id: int,
    body: EducatorLevelIn,
    db: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    row = db.get(EducatorLevel, level_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row



# --- admin: rooms -----------------------------------------------------
@router.get("/api/admin/rooms", response_model=list[RoomOut])
def admin_list_rooms(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(select(Room).order_by(Room.name)).all()


@router.post("/api/admin/rooms", response_model=RoomOut)
def admin_create_room(
    body: RoomIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = Room(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/api/admin/rooms/{room_id}", response_model=RoomOut)
def admin_update_room(
    room_id: int, body: RoomIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = db.get(Room, room_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/api/admin/rooms/{room_id}")
def admin_deactivate_room(
    room_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    # Rooms are never hard-deleted (bookings may reference them) — deactivate.
    row = db.get(Room, room_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    row.active = False
    db.commit()
    return {"ok": True}



# --- admin: service types (named sessions/additional services) -------------
@router.get("/api/admin/service-types", response_model=list[ServiceTypeOut])
def admin_list_service_types(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(select(ServiceType).order_by(ServiceType.category, ServiceType.sort_order, ServiceType.name)).all()


@router.post("/api/admin/service-types", response_model=ServiceTypeOut)
def admin_create_service_type(
    body: ServiceTypeIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = ServiceType(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/api/admin/service-types/{service_type_id}", response_model=ServiceTypeOut)
def admin_update_service_type(
    service_type_id: int, body: ServiceTypeIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = db.get(ServiceType, service_type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/api/admin/service-types/{service_type_id}")
def admin_deactivate_service_type(
    service_type_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = db.get(ServiceType, service_type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    row.active = False
    db.commit()
    return {"ok": True}



# --- admin: users (educators/admins) --------------------------------------
def _user_out(db: Session, row: User) -> UserOut:
    out = UserOut.model_validate(row, from_attributes=True)
    out.has_photo = row.photo is not None
    form = db.scalar(select(EducatorOnboardingForm).where(EducatorOnboardingForm.user_id == row.id))
    out.onboarding_status = form.status if form else None
    return out


@router.get("/api/admin/users", response_model=list[UserOut])
def admin_list_users(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    rows = db.scalars(select(User).order_by(User.full_name)).all()
    statuses = {f.user_id: f.status for f in db.scalars(select(EducatorOnboardingForm)).all()}
    out = []
    for r in rows:
        u = UserOut.model_validate(r, from_attributes=True)
        u.has_photo = r.photo is not None
        u.onboarding_status = statuses.get(r.id)
        out.append(u)
    return out


@router.post("/api/admin/users", response_model=UserOut)
def admin_create_user(
    body: UserIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(status_code=409, detail="Email already in use")
    row = User(
        email=body.email.lower(),
        full_name=body.full_name,
        role=body.role,
        level_id=body.level_id,
        password_hash=auth.hash_password(body.password),
        bio=body.bio,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    # New educators get the onboarding questionnaire automatically, same as
    # new learners; admins don't (nothing to onboard). `send_onboarding=False`
    # imports someone already working here without firing the invite.
    if row.role == "educator" and body.send_onboarding:
        form = educator_onboarding.get_or_create_form(db, row)
        educator_onboarding.send_invite(db, row, form)
    return _user_out(db, row)


@router.put("/api/admin/users/{user_id}", response_model=UserOut)
def admin_update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    data = body.model_dump(exclude_unset=True)
    if "password" in data:
        pw = data.pop("password")
        if pw:
            row.password_hash = auth.hash_password(pw)
    if "image_consent" in data:
        _set_image_consent(row, data.pop("image_consent"), source="admin")
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return _user_out(db, row)


def _set_image_consent(row: User, granted: bool, *, source: str) -> None:
    """Record or withdraw consent to use someone's photo/bio in the app.
    Withdrawing also removes the photo — consent is the lawful basis for
    holding it (04/09/2026 privacy review)."""
    if granted:
        row.image_consent_at = datetime.now(UTC)
        row.image_consent_source = source
    else:
        row.image_consent_at = None
        row.image_consent_source = None
        row.photo = None
        row.photo_content_type = None


@router.get("/api/users/{user_id}/photo")
def user_photo(user_id: int, db: Session = Depends(get_session), _user: User = Depends(require_user)):
    """Serve a staff headshot to signed-in colleagues (never public)."""
    row = db.get(User, user_id)
    if row is None or row.photo is None:
        raise HTTPException(status_code=404, detail="No photo")
    return Response(
        content=row.photo,
        media_type=row.photo_content_type or "image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )


_MAX_PHOTO_BYTES = 5 * 1024 * 1024
_ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/api/users/{user_id}/photo", response_model=UserOut)
async def upload_user_photo(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    """Upload/replace a headshot — your own, or anyone's if you're an admin.
    Storing a photo records image consent if it isn't already on file."""
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    if user.role != "admin" and user.id != row.id:
        raise HTTPException(status_code=403, detail="Not your profile")
    if file.content_type not in _ALLOWED_PHOTO_TYPES:
        raise HTTPException(status_code=422, detail="Photo must be a JPEG, PNG or WebP image")
    content = await file.read()
    if len(content) > _MAX_PHOTO_BYTES:
        raise HTTPException(status_code=422, detail="Photo must be under 5 MB")
    row.photo = content
    row.photo_content_type = file.content_type
    if row.image_consent_at is None:
        _set_image_consent(row, True, source="self" if user.id == row.id else "admin")
    db.commit()
    db.refresh(row)
    return _user_out(db, row)


@router.delete("/api/users/{user_id}/photo", response_model=UserOut)
def delete_user_photo(user_id: int, db: Session = Depends(get_session), user: User = Depends(require_user)):
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    if user.role != "admin" and user.id != row.id:
        raise HTTPException(status_code=403, detail="Not your profile")
    row.photo = None
    row.photo_content_type = None
    db.commit()
    db.refresh(row)
    return _user_out(db, row)


@router.get("/api/me/profile", response_model=UserOut)
def my_profile(db: Session = Depends(get_session), user: User = Depends(require_user)):
    return _user_out(db, user)


@router.put("/api/me/profile", response_model=UserOut)
def update_my_profile(
    body: ProfileUpdateIn, db: Session = Depends(get_session), user: User = Depends(require_user)
):
    """Everyone may edit their own bio and grant/withdraw image consent."""
    data = body.model_dump(exclude_unset=True)
    if "image_consent" in data:
        _set_image_consent(user, data.pop("image_consent"), source="self")
    if "bio" in data:
        user.bio = data["bio"]
    db.commit()
    db.refresh(user)
    return _user_out(db, user)


@router.delete("/api/admin/users/{user_id}")
def admin_deactivate_user(
    user_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    # Deactivate, never hard-delete — bookings/invoices may reference this user.
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    row.active = False
    db.commit()
    return {"ok": True}



# --- admin: price list (time-versioned, never edited in place) ------------
@router.get("/api/admin/price-list", response_model=list[PriceListEntryOut])
def admin_list_price_list(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(
        select(PriceListEntry).order_by(PriceListEntry.level_id, PriceListEntry.duration_minutes, PriceListEntry.valid_from)
    ).all()


@router.post("/api/admin/price-list", response_model=PriceListEntryOut)
def admin_create_price_entry(
    body: PriceListEntryIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = PriceListEntry(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row



# --- admin: facility hours / closures --------------------------------------
@router.get("/api/admin/facility-hours", response_model=list[FacilityHoursOut])
def admin_list_hours(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(select(FacilityHours).order_by(FacilityHours.weekday)).all()


@router.put("/api/admin/facility-hours", response_model=FacilityHoursOut)
def admin_upsert_hours(
    body: FacilityHoursIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = db.scalar(select(FacilityHours).where(FacilityHours.weekday == body.weekday))
    if row is None:
        row = FacilityHours(**body.model_dump())
        db.add(row)
    else:
        row.open_time = body.open_time
        row.close_time = body.close_time
    db.commit()
    db.refresh(row)
    return row


@router.delete("/api/admin/facility-hours/{weekday}")
def admin_delete_hours(weekday: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    """Mark a weekday closed — no hours row means no bookings that day.
    Idempotent: deleting an already-closed day is a no-op success."""
    row = db.scalar(select(FacilityHours).where(FacilityHours.weekday == weekday))
    if row is not None:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.get("/api/admin/closures", response_model=list[FacilityClosureOut])
def admin_list_closures(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(select(FacilityClosure).order_by(FacilityClosure.date)).all()


@router.post("/api/admin/closures", response_model=FacilityClosureOut)
def admin_create_closure(
    body: FacilityClosureIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = FacilityClosure(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/api/admin/closures/{closure_id}")
def admin_delete_closure(
    closure_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = db.get(FacilityClosure, closure_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


