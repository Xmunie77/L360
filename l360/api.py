"""FastAPI app for Learning 360° (l360).

Serves the built React SPA and a JSON API:
  POST /api/login   {email,password}  -> sets session cookie
  POST /api/logout
  GET  /api/session                   -> {authed, user}
  GET  /api/me
  GET  /api/rooms | /api/educators | /api/clients | /api/price-list/current
  /api/admin/*  (admin only) — educator-levels, users, clients, rooms,
                price-list, facility-hours, closures
  GET  /health
"""
from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from datetime import date as date_cls
from datetime import UTC, datetime, timedelta

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
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

assert_secure_config()

# Error monitoring — inert without the SENTRY_DSN Fly secret (P0-3).
from l360.config import SENTRY_DSN  # noqa: E402

if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0, send_default_pii=False)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Creates the SQLite schema for local/dev so `uvicorn l360.api:app` works
    # on a clean checkout. No-op on Postgres — that schema is owned by gated
    # Alembic, never mutated on boot.
    init_db()
    yield


app = FastAPI(title="Learning 360°", lifespan=lifespan)

if not IS_POSTGRES:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# --- auth dependencies -------------------------------------------------
def _current_user(db: Session, l360_session: str | None) -> User | None:
    payload = auth.read_session_cookie(l360_session)
    if not payload:
        return None
    user = db.get(User, payload.get("uid"))
    if user is None or not user.active:
        return None
    # Sessions die when the password changes: the cookie carries a
    # fingerprint of the password hash it was issued against (P1-3).
    if payload.get("pw") != auth.password_fingerprint(user.password_hash):
        return None
    return user


def require_user(
    l360_session: str | None = Cookie(default=None), db: Session = Depends(get_session)
) -> User:
    user = _current_user(db, l360_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# --- health / auth routes -----------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


_LOCKOUT_THRESHOLD = 5
_LOCKOUT_MINUTES = 15


@app.post("/api/login")
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


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}


@app.get("/api/session")
def session(l360_session: str | None = Cookie(default=None), db: Session = Depends(get_session)):
    user = _current_user(db, l360_session)
    return {"authed": user is not None}


_RESET_TOKEN_TTL = timedelta(hours=1)


@app.post("/api/forgot-password")
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


@app.post("/api/reset-password")
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


@app.get("/api/me", response_model=MeResp)
def me(user: User = Depends(require_user)):
    return user


@app.post("/api/me/password")
def change_my_password(body: ChangePasswordIn, db: Session = Depends(get_session), user: User = Depends(require_user)):
    """Self-service password change from the Profile page — requires the
    current password, unlike the admin reset in /api/admin/users."""
    if not auth.verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=403, detail="Current password is wrong.")
    user.password_hash = auth.hash_password(body.new_password)
    db.commit()
    return {"ok": True}


# --- read-only lists for any authed user ------------------------------
@app.get("/api/rooms", response_model=list[RoomOut])
def list_rooms_ro(db: Session = Depends(get_session), _user: User = Depends(require_user)):
    return db.scalars(select(Room).where(Room.active == True).order_by(Room.name)).all()  # noqa: E712


@app.get("/api/educators", response_model=list[UserOut])
def list_educators_ro(db: Session = Depends(get_session), _user: User = Depends(require_user)):
    # Anyone with a level assigned delivers sessions and is bookable — not
    # just role="educator". An admin who's also a founder/educator shows up
    # here too once they're given a level.
    return db.scalars(
        select(User).where(User.level_id.is_not(None), User.active == True).order_by(User.full_name)  # noqa: E712
    ).all()


@app.get("/api/session-types", response_model=list[ServiceTypeOut])
def list_session_types_ro(db: Session = Depends(get_session), _user: User = Depends(require_user)):
    # Only bookable "session" items — "additional_service" ones (flashcards,
    # etc.) aren't calendar bookings, so they're never offered here.
    return db.scalars(
        select(ServiceType)
        .where(ServiceType.category == "session", ServiceType.active == True)  # noqa: E712
        .order_by(ServiceType.sort_order, ServiceType.name)
    ).all()


@app.get("/api/clients", response_model=list[ClientBrief])
def list_clients_ro(db: Session = Depends(get_session), _user: User = Depends(require_user)):
    return db.scalars(
        select(Client).where(Client.active == True).order_by(Client.guardian_surname, Client.guardian_first_name)
    ).all()  # noqa: E712


@app.get("/api/price-list/current", response_model=list[PriceListEntryOut])
def price_list_current(
    as_of: date_cls | None = None,
    db: Session = Depends(get_session),
    _user: User = Depends(require_user),
):
    """For each (level, duration), the entry with the latest valid_from <= as_of."""
    as_of = as_of or date_cls.today()
    rows = db.scalars(select(PriceListEntry).where(PriceListEntry.valid_from <= as_of)).all()
    latest: dict[tuple[int, int], PriceListEntry] = {}
    for row in rows:
        key = (row.level_id, row.duration_minutes)
        if key not in latest or row.valid_from > latest[key].valid_from:
            latest[key] = row
    return list(latest.values())


# --- admin: educator levels ----------------------------------------------
@app.get("/api/admin/educator-levels", response_model=list[EducatorLevelOut])
def admin_list_levels(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(select(EducatorLevel).order_by(EducatorLevel.sort_order)).all()


@app.post("/api/admin/educator-levels", response_model=EducatorLevelOut)
def admin_create_level(
    body: EducatorLevelIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = EducatorLevel(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.put("/api/admin/educator-levels/{level_id}", response_model=EducatorLevelOut)
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
@app.get("/api/admin/rooms", response_model=list[RoomOut])
def admin_list_rooms(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(select(Room).order_by(Room.name)).all()


@app.post("/api/admin/rooms", response_model=RoomOut)
def admin_create_room(
    body: RoomIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = Room(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.put("/api/admin/rooms/{room_id}", response_model=RoomOut)
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


@app.delete("/api/admin/rooms/{room_id}")
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
@app.get("/api/admin/service-types", response_model=list[ServiceTypeOut])
def admin_list_service_types(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(select(ServiceType).order_by(ServiceType.category, ServiceType.sort_order, ServiceType.name)).all()


@app.post("/api/admin/service-types", response_model=ServiceTypeOut)
def admin_create_service_type(
    body: ServiceTypeIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = ServiceType(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.put("/api/admin/service-types/{service_type_id}", response_model=ServiceTypeOut)
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


@app.delete("/api/admin/service-types/{service_type_id}")
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
    form = db.scalar(select(EducatorOnboardingForm).where(EducatorOnboardingForm.user_id == row.id))
    out.onboarding_status = form.status if form else None
    return out


@app.get("/api/admin/users", response_model=list[UserOut])
def admin_list_users(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    rows = db.scalars(select(User).order_by(User.full_name)).all()
    statuses = {f.user_id: f.status for f in db.scalars(select(EducatorOnboardingForm)).all()}
    out = []
    for r in rows:
        u = UserOut.model_validate(r, from_attributes=True)
        u.onboarding_status = statuses.get(r.id)
        out.append(u)
    return out


@app.post("/api/admin/users", response_model=UserOut)
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
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    # New educators get the onboarding questionnaire automatically, same as
    # new learners; admins don't (nothing to onboard).
    if row.role == "educator":
        form = educator_onboarding.get_or_create_form(db, row)
        educator_onboarding.send_invite(db, row, form)
    return _user_out(db, row)


@app.put("/api/admin/users/{user_id}", response_model=UserOut)
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
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/api/admin/users/{user_id}")
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


# --- admin: clients ---------------------------------------------------
def _client_out(row: Client, status: str | None) -> ClientOut:
    out = ClientOut.model_validate(row, from_attributes=True)
    out.onboarding_status = status
    return out


def _onboarding_status(db: Session, client_id: int) -> str | None:
    form = db.scalar(select(OnboardingForm).where(OnboardingForm.client_id == client_id))
    return form.status if form else None


@app.get("/api/admin/clients", response_model=list[ClientOut])
def admin_list_clients(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    rows = db.scalars(select(Client).order_by(Client.guardian_surname, Client.guardian_first_name)).all()
    statuses = {f.client_id: f.status for f in db.scalars(select(OnboardingForm)).all()}
    return [_client_out(r, statuses.get(r.id)) for r in rows]


@app.get("/api/admin/clients/{client_id}", response_model=ClientOut)
def admin_get_client(client_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    row = db.get(Client, client_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _client_out(row, _onboarding_status(db, row.id))


@app.post("/api/admin/clients", response_model=ClientOut)
def admin_create_client(
    body: ClientIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = Client(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    # The onboarding questionnaire goes out automatically as soon as the
    # guardian's basic details are in — the admin doesn't have to remember.
    form = onboarding.get_or_create_form(db, row)
    onboarding.send_invite(db, row, form)
    return _client_out(row, form.status)


@app.put("/api/admin/clients/{client_id}", response_model=ClientOut)
def admin_update_client(
    client_id: int,
    body: ClientIn,
    db: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    row = db.get(Client, client_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    # exclude_unset so a caller that doesn't know about newer optional
    # columns (e.g. the onboarding-sourced guardian-2/allergy fields) can't
    # silently wipe them — an explicit null still clears a field.
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return _client_out(row, _onboarding_status(db, row.id))


@app.get("/api/admin/clients/{client_id}/onboarding", response_model=OnboardingAdminOut | None)
def admin_get_onboarding(client_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    if db.get(Client, client_id) is None:
        raise HTTPException(status_code=404, detail="Not found")
    form = db.scalar(select(OnboardingForm).where(OnboardingForm.client_id == client_id))
    if form is None:
        return None
    return OnboardingAdminOut(link=onboarding.form_link(form), **{
        k: getattr(form, k)
        for k in OnboardingAdminOut.model_fields
        if k != "link"
    })


@app.post("/api/admin/clients/{client_id}/onboarding/send", response_model=OnboardingAdminOut)
def admin_send_onboarding(client_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    """Send (or re-send) the onboarding questionnaire email — e.g. for a
    client created before this feature, or a guardian who lost the link."""
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Not found")
    form = onboarding.get_or_create_form(db, client)
    if form.status == "submitted":
        raise HTTPException(status_code=409, detail="This client's onboarding form is already submitted.")
    if not client.email:
        raise HTTPException(status_code=409, detail="This client has no email address on record.")
    onboarding.send_invite(db, client, form)
    return admin_get_onboarding(client_id, db, _admin)




# --- admin: invoice template settings + PDF --------------------------------
_INVOICE_KEY_MAP = {
    "name": "invoice_name", "address": "invoice_address", "vat": "invoice_vat",
    "bank": "invoice_bank", "contact": "invoice_contact", "footer": "invoice_footer",
}


@app.get("/api/admin/invoice-settings", response_model=InvoiceSettingsOut)
def admin_get_invoice_settings(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    head = invoice_pdf.letterhead()
    return InvoiceSettingsOut(**{field: head[key] for field, key in _INVOICE_KEY_MAP.items()})


@app.put("/api/admin/invoice-settings", response_model=InvoiceSettingsOut)
def admin_save_invoice_settings(
    body: InvoiceSettingsIn, db: Session = Depends(get_session), admin: User = Depends(require_admin)
):
    for field, key in _INVOICE_KEY_MAP.items():
        _upsert_setting(db, key, getattr(body, field).strip())
    db.commit()
    return admin_get_invoice_settings(db, admin)


@app.get("/api/admin/invoice-settings/sample-pdf")
def admin_sample_invoice_pdf(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    """A dummy invoice rendered with the CURRENT letterhead — so template
    changes can be eyeballed without touching a real invoice."""
    from datetime import date as _date

    data = invoice_pdf.InvoicePdfData(
        number="SAMPLE-0000",
        issue_date=_date.today(),
        learner_name="Sample Learner",
        attn="Alex and Sam Parent",
        bill_address="1, Example Street\nSwatar",
        lines=[
            invoice_pdf.InvoiceLinePdf("Consultant Office Session — 2026-08-04 — Maria Educator", 1, 3500, 3500),
            invoice_pdf.InvoiceLinePdf("Consultant Office Session — 2026-08-11 — Maria Educator", 1, 3500, 3500),
        ],
        total_cents=7000,
        paid_cents=0,
    )
    return Response(
        content=invoice_pdf.build_invoice_pdf(data),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="sample-invoice.pdf"'},
    )


def _invoice_pdf_data(db: Session, inv: Invoice) -> invoice_pdf.InvoicePdfData:
    client = db.get(Client, inv.client_id)
    lines = db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)).all()
    pdf_lines = []
    for line in lines:
        desc = line.description
        # Lines generated before 30/08/2026 lack the educator name — add it
        # from the booking at render time so older invoices carry it too.
        if line.booking_id:
            b = db.get(Booking, line.booking_id)
            educator = db.get(User, b.educator_id) if b else None
            if educator and educator.full_name not in desc:
                desc = f"{desc} — {educator.full_name}"
        pdf_lines.append(invoice_pdf.InvoiceLinePdf(desc, line.quantity, line.unit_price_cents, line.amount_cents))
    attn_names = [client.guardian_name] if client else []
    if client and client.guardian2_name:
        attn_names.append(client.guardian2_name)
    paid = inv.total_cents - reconciliation.outstanding_cents(db, inv)
    return invoice_pdf.InvoicePdfData(
        number=inv.number or "DRAFT",
        issue_date=(inv.issued_at.date() if inv.issued_at else inv.created_at.date()),
        learner_name=(client.child_name or client.guardian_name) if client else "?",
        attn=" and ".join(attn_names),
        bill_address=client.address if client else None,
        lines=pdf_lines,
        total_cents=inv.total_cents,
        paid_cents=paid,
    )


@app.get("/api/admin/invoices/{invoice_id}/pdf")
def admin_invoice_pdf(invoice_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Not found")
    data = _invoice_pdf_data(db, inv)
    filename = f"Invoice {data.number}.pdf" if inv.number else f"Invoice DRAFT-{inv.id}.pdf"
    return Response(
        content=invoice_pdf.build_invoice_pdf(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@app.get("/api/admin/email-settings", response_model=EmailSettingsOut)
def admin_get_email_settings(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    cfg = notify.smtp_config()
    return EmailSettingsOut(
        host=cfg["host"], port=cfg["port"], user=cfg["user"], email_from=cfg["from"],
        password_set=bool(cfg["password"]),
    )


@app.put("/api/admin/email-settings", response_model=EmailSettingsOut)
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


@app.post("/api/admin/email-settings/test", response_model=EmailTestOut)
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



# --- educator onboarding ----------------------------------------------------
def _educator_onboarding_out(form: EducatorOnboardingForm) -> EducatorOnboardingAdminOut:
    return EducatorOnboardingAdminOut(
        id=form.id, user_id=form.user_id, status=form.status, source=form.source,
        link=educator_onboarding.form_link(form), sent_at=form.sent_at,
        submitted_at=form.submitted_at, signature_name=form.signature_name,
        signed_date=form.signed_date, answers=form.answers, internal=form.internal,
    )


@app.get("/api/admin/users/{user_id}/onboarding", response_model=EducatorOnboardingAdminOut | None)
def admin_get_educator_onboarding(user_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="Not found")
    form = db.scalar(select(EducatorOnboardingForm).where(EducatorOnboardingForm.user_id == user_id))
    return _educator_onboarding_out(form) if form else None


@app.post("/api/admin/users/{user_id}/onboarding/send", response_model=EducatorOnboardingAdminOut)
def admin_send_educator_onboarding(user_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Not found")
    if user.role != "educator":
        raise HTTPException(status_code=409, detail="Onboarding forms are for educator accounts.")
    form = educator_onboarding.get_or_create_form(db, user)
    if form.status == "submitted":
        raise HTTPException(status_code=409, detail="This educator's onboarding form is already submitted.")
    educator_onboarding.send_invite(db, user, form)
    return _educator_onboarding_out(form)



@app.put("/api/admin/users/{user_id}/onboarding/checklist", response_model=EducatorOnboardingAdminOut)
def admin_save_educator_checklist(
    user_id: int, body: EducatorChecklistIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    """Save the section-15 internal checklist + final approval. Works from
    the moment the educator account exists — the checks (interview, identity,
    references) run alongside the educator filling in their own form, so the
    checklist doesn't wait for submission."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Not found")
    if user.role != "educator":
        raise HTTPException(status_code=409, detail="Onboarding checklists are for educator accounts.")
    form = educator_onboarding.get_or_create_form(db, user)
    form.internal = body.model_dump()
    db.commit()
    return _educator_onboarding_out(form)



@app.get("/api/admin/users/{user_id}/onboarding/contract")
def admin_generate_contract(user_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    """Pre-filled tutor Services Agreement (.docx) from the submitted
    onboarding form — a starting point for the written agreement, reviewed
    and signed on paper (rates, founders' IDs and the foundation email stay
    blank for hand-completion)."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Not found")
    form = db.scalar(select(EducatorOnboardingForm).where(EducatorOnboardingForm.user_id == user_id))
    if form is None or form.status != "submitted" or not form.answers:
        raise HTTPException(status_code=409, detail="The educator's onboarding form must be submitted first — the contract is pre-filled from it.")
    data = contract.build_contract(form.answers)
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in (user.full_name or "tutor")).strip() or "tutor"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="Services Agreement - {safe_name}.docx"'},
    )


def _educator_form_by_token(db: Session, token: str) -> tuple[EducatorOnboardingForm, User]:
    # Public by design — the educator has no session yet when they fill this
    # in; the unguessable token is the auth (same pattern as the client form).
    form = db.scalar(select(EducatorOnboardingForm).where(EducatorOnboardingForm.token == token))
    user = db.get(User, form.user_id) if form else None
    if form is None or user is None or not user.active:
        raise HTTPException(status_code=404, detail="Unknown or expired onboarding link")
    return form, user


@app.get("/api/educator-onboarding/{token}", response_model=EducatorOnboardingPrefillOut)
def get_educator_onboarding(token: str, db: Session = Depends(get_session)):
    form, user = _educator_form_by_token(db, token)
    return EducatorOnboardingPrefillOut(status=form.status, full_name=user.full_name, email=user.email)


@app.post("/api/educator-onboarding/{token}")
def submit_educator_onboarding(token: str, body: EducatorOnboardingSubmitIn, db: Session = Depends(get_session)):
    form, user = _educator_form_by_token(db, token)
    if form.status == "submitted":
        raise HTTPException(status_code=409, detail="This onboarding form has already been submitted.")
    educator_onboarding.apply_submission(db, form, body)
    notify.send_once(
        db,
        to=user.email,
        subject="Learning 360\u00b0 — onboarding form received",
        body=(
            f"Dear {user.full_name},\n\n"
            "Thank you — we've received your educator onboarding form. We'll "
            "review it and complete the remaining checks, and be in touch about "
            "next steps.\n\n"
            "Warm regards,\n"
            "Learning 360\u00b0 Foundation\n"
            "Swatar, Malta"
        ),
        booking_id=None,
        user_id=user.id,
        kind="educator_onboarding_submitted",
        dedupe_key=f"educator_onboarding_submitted:{form.id}",
    )
    return {"ok": True}


# --- public onboarding questionnaire ---------------------------------------
def _form_by_token(db: Session, token: str) -> tuple[OnboardingForm, Client]:
    # Deliberately NOT behind require_user — the guardian has no account.
    # The unguessable token is the auth, same pattern as the iCal feed.
    form = db.scalar(select(OnboardingForm).where(OnboardingForm.token == token))
    client = db.get(Client, form.client_id) if form else None
    if form is None or client is None or not client.active:
        raise HTTPException(status_code=404, detail="Unknown or expired onboarding link")
    return form, client


@app.get("/api/onboarding/{token}", response_model=OnboardingPrefillOut)
def get_onboarding(token: str, db: Session = Depends(get_session)):
    form, client = _form_by_token(db, token)
    return OnboardingPrefillOut(
        status=form.status,
        **{f: getattr(client, f) for f in onboarding.CLIENT_FIELDS},
    )


@app.post("/api/onboarding/{token}")
def submit_onboarding(token: str, body: OnboardingSubmitIn, db: Session = Depends(get_session)):
    form, client = _form_by_token(db, token)
    if form.status == "submitted":
        raise HTTPException(status_code=409, detail="This onboarding form has already been submitted.")
    onboarding.apply_submission(db, client, form, body)
    notify.send_once(
        db,
        to=client.email,
        subject="Learning 360° — onboarding form received",
        body=(
            f"Dear {client.guardian_first_name} {client.guardian_surname},\n\n"
            f"Thank you — we've received your onboarding form for {client.child_name}.\n"
            "We look forward to welcoming you to Learning 360° Foundation.\n\n"
            "Warm regards,\n"
            "Learning 360° Foundation\n"
            "Swatar, Malta"
        ),
        booking_id=None,
        user_id=None,
        kind="onboarding_submitted",
        dedupe_key=f"onboarding_submitted:{form.id}",
    )
    return {"ok": True}


# --- admin: price list (time-versioned, never edited in place) ------------
@app.get("/api/admin/price-list", response_model=list[PriceListEntryOut])
def admin_list_price_list(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(
        select(PriceListEntry).order_by(PriceListEntry.level_id, PriceListEntry.duration_minutes, PriceListEntry.valid_from)
    ).all()


@app.post("/api/admin/price-list", response_model=PriceListEntryOut)
def admin_create_price_entry(
    body: PriceListEntryIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = PriceListEntry(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# --- admin: facility hours / closures --------------------------------------
@app.get("/api/admin/facility-hours", response_model=list[FacilityHoursOut])
def admin_list_hours(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(select(FacilityHours).order_by(FacilityHours.weekday)).all()


@app.put("/api/admin/facility-hours", response_model=FacilityHoursOut)
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


@app.get("/api/admin/closures", response_model=list[FacilityClosureOut])
def admin_list_closures(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    return db.scalars(select(FacilityClosure).order_by(FacilityClosure.date)).all()


@app.post("/api/admin/closures", response_model=FacilityClosureOut)
def admin_create_closure(
    body: FacilityClosureIn, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = FacilityClosure(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/api/admin/closures/{closure_id}")
def admin_delete_closure(
    closure_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)
):
    row = db.get(FacilityClosure, closure_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


# --- bookings ------------------------------------------------------------
def _client_label(client: Client) -> str:
    name = f"{client.guardian_first_name} {client.guardian_surname}"
    return f"{name} ({client.child_name})" if client.child_name else name


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


@app.get("/api/bookings", response_model=list[BookingOut])
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
    return [_booking_out(db, b) for b in rows]


@app.get("/api/bookings/next-available", response_model=NextAvailableOut)
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


@app.get("/api/bookings/{booking_id}", response_model=BookingOut)
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


@app.post("/api/bookings", response_model=BookingOut)
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


@app.post("/api/bookings/series", response_model=BookingSeriesOut)
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
        created=[_booking_out(db, b) for b in created],
        skipped=skipped,
    )


@app.patch("/api/bookings/{booking_id}", response_model=BookingOut)
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


@app.post("/api/bookings/{booking_id}/cancel", response_model=BookingOut)
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


@app.post("/api/bookings/{booking_id}/status", response_model=BookingOut)
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


# --- billing ------------------------------------------------------------
def _invoice_out(db: Session, inv: Invoice) -> InvoiceOut:
    client = db.get(Client, inv.client_id)
    return InvoiceOut(
        id=inv.id,
        client_id=inv.client_id,
        client_label=_client_label(client) if client else "?",
        number=inv.number,
        period_start=inv.period_start,
        period_end=inv.period_end,
        status=inv.status,
        total_cents=inv.total_cents,
        outstanding_cents=reconciliation.outstanding_cents(db, inv),
        issued_at=inv.issued_at,
        due_date=inv.due_date,
        notes=inv.notes,
        created_at=inv.created_at,
    )


@app.post("/api/admin/billing/run", response_model=BillingRunOut)
def admin_billing_run(
    body: BillingRunIn, db: Session = Depends(get_session), admin: User = Depends(require_admin)
):
    clients = db.scalars(select(Client).where(Client.active == True)).all()  # noqa: E712
    created: list[Invoice] = []
    skipped: list[int] = []
    for c in clients:
        try:
            inv = billing_logic.generate_draft_invoice(
                db, client_id=c.id, period_start=body.period_start, period_end=body.period_end, created_by=admin.id
            )
            created.append(inv)
        except BillingError:
            skipped.append(c.id)
    return BillingRunOut(created=[_invoice_out(db, i) for i in created], skipped_clients=skipped)


@app.get("/api/admin/invoices", response_model=list[InvoiceOut])
def admin_list_invoices(
    status: str | None = None,
    client_id: int | None = None,
    db: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    q = select(Invoice)
    if status is not None:
        q = q.where(Invoice.status == status)
    if client_id is not None:
        q = q.where(Invoice.client_id == client_id)
    rows = db.scalars(q.order_by(Invoice.created_at.desc())).all()
    return [_invoice_out(db, i) for i in rows]


@app.get("/api/admin/invoices/{invoice_id}", response_model=InvoiceDetailOut)
def admin_get_invoice(invoice_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Not found")
    lines = db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)).all()
    base = _invoice_out(db, inv)
    return InvoiceDetailOut(**base.model_dump(), lines=[InvoiceLineOut.model_validate(l, from_attributes=True) for l in lines])


@app.post("/api/admin/invoices/{invoice_id}/issue", response_model=InvoiceOut)
def admin_issue_invoice(invoice_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        billing_logic.issue_invoice(db, inv)
    except BillingError as e:
        raise HTTPException(status_code=409, detail=e.reason)

    client = db.get(Client, inv.client_id)
    if client and client.email:
        pdf_bytes = invoice_pdf.build_invoice_pdf(_invoice_pdf_data(db, inv))
        notify.send_once(
            db,
            to=client.email,
            subject=f"Invoice {inv.number} — €{inv.total_cents / 100:.2f}",
            body=(
                f"Invoice {inv.number} for the period {inv.period_start} to {inv.period_end} is attached.\n"
                f"Total: €{inv.total_cents / 100:.2f} (VAT exempt). Due: {inv.due_date}.\n"
                f"Please use \"{inv.number}\" as your payment reference."
            ),
            booking_id=None,
            user_id=None,
            kind="invoice_issued",
            dedupe_key=f"invoice_issued:{inv.id}",
            attachment=(f"Invoice {inv.number}.pdf", pdf_bytes),
        )
    return _invoice_out(db, inv)


# --- payments / reconciliation ---------------------------------------------
@app.post("/api/admin/payments/sync", response_model=SyncResultOut)
def admin_sync_payments(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    from l360.payments.revolut import RevolutProvider

    last = db.scalar(select(BankTxn).order_by(BankTxn.txn_date.desc()))
    since = last.txn_date if last else datetime.now(UTC) - timedelta(days=90)

    try:
        txns = RevolutProvider().fetch_transactions(since)
    except ProviderNotConfigured as e:
        raise HTTPException(status_code=409, detail=str(e))

    new_rows = reconciliation.import_transactions(db, txns)
    matched = 0
    for row in new_rows:
        if reconciliation.try_match(db, row) is not None:
            matched += 1
    unmatched = len(new_rows) - matched
    return SyncResultOut(imported=len(new_rows), matched=matched, unmatched=unmatched)


@app.get("/api/admin/payments/unmatched", response_model=list[BankTxnOut])
def admin_unmatched_txns(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    rows = db.scalars(
        select(BankTxn).where(BankTxn.payment_id.is_(None)).order_by(BankTxn.txn_date.desc())
    ).all()
    return rows


@app.post("/api/admin/payments/manual-match", response_model=PaymentOut)
def admin_manual_match(
    body: ManualMatchIn, db: Session = Depends(get_session), admin: User = Depends(require_admin)
):
    txn = db.get(BankTxn, body.bank_txn_id)
    invoice = db.get(Invoice, body.invoice_id)
    if txn is None or invoice is None:
        raise HTTPException(status_code=404, detail="Not found")
    if txn.payment_id is not None:
        raise HTTPException(status_code=409, detail="Transaction already matched")
    payment = reconciliation.manual_match(db, bank_txn=txn, invoice=invoice, created_by=admin.id)
    return payment


@app.post("/api/admin/payments/record", response_model=PaymentOut)
def admin_record_payment(
    body: RecordPaymentIn, db: Session = Depends(get_session), admin: User = Depends(require_admin)
):
    invoice = db.get(Invoice, body.invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Not found")
    if invoice.status not in ("issued", "partially_paid"):
        raise HTTPException(status_code=409, detail=f"Invoice is {invoice.status}, not payable")
    payment = reconciliation.record_manual_payment(
        db,
        invoice=invoice,
        amount_cents=body.amount_cents,
        method=body.method,
        received_at=body.received_at,
        created_by=admin.id,
        external_ref=body.external_ref,
        received_by_id=body.received_by_id,
    )
    return payment


# --- statements / reports -------------------------------------------------
@app.get("/api/admin/statements/client/{client_id}", response_model=ClientStatementOut)
def admin_client_statement(
    client_id: int,
    period_start: date_cls,
    period_end: date_cls,
    db: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Not found")
    s = statements_logic.client_statement(db, client_id=client_id, period_start=period_start, period_end=period_end)
    return ClientStatementOut(
        client_id=s.client_id,
        client_label=_client_label(client),
        period_start=s.period_start,
        period_end=s.period_end,
        opening_balance_cents=s.opening_balance_cents,
        invoices=[StatementInvoiceLineOut(**vars(i)) for i in s.invoices],
        payments=[StatementPaymentLineOut(**vars(p)) for p in s.payments],
        closing_balance_cents=s.closing_balance_cents,
    )


def _require_self_or_admin(target_user_id: int, user: User) -> None:
    if user.role != "admin" and user.id != target_user_id:
        raise HTTPException(status_code=403, detail="Not your summary")


@app.get("/api/statements/educator/{educator_id}/summary", response_model=EducatorSummaryOut)
def educator_summary_route(
    educator_id: int,
    period_start: date_cls,
    period_end: date_cls,
    db: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    _require_self_or_admin(educator_id, user)
    educator = db.get(User, educator_id)
    if educator is None:
        raise HTTPException(status_code=404, detail="Not found")
    s = statements_logic.educator_summary(db, educator_id=educator_id, period_start=period_start, period_end=period_end)
    return EducatorSummaryOut(
        educator_id=s.educator_id,
        educator_name=educator.full_name,
        period_start=s.period_start,
        period_end=s.period_end,
        sessions=[SummarySessionLineOut(**vars(line)) for line in s.sessions],
        total_payable_cents=s.total_payable_cents,
    )


@app.get("/api/admin/reports/utilisation", response_model=list[RoomUtilisationOut])
def admin_utilisation_report(
    period_start: date_cls,
    period_end: date_cls,
    db: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    rows = statements_logic.utilisation_by_room(db, period_start=period_start, period_end=period_end)
    return [RoomUtilisationOut(**vars(r)) for r in rows]


# --- iCal feed -----------------------------------------------------------
@app.get("/api/me/calendar-token", response_model=CalendarTokenOut | None)
def get_my_calendar_token(db: Session = Depends(get_session), user: User = Depends(require_user)):
    row = db.scalar(select(CalendarToken).where(CalendarToken.user_id == user.id, CalendarToken.revoked_at.is_(None)))
    if row is None:
        return None
    return CalendarTokenOut(token=row.token, feed_path=f"/api/calendar/{row.token}.ics")


@app.post("/api/me/calendar-token", response_model=CalendarTokenOut)
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


@app.delete("/api/me/calendar-token")
def revoke_calendar_token(db: Session = Depends(get_session), user: User = Depends(require_user)):
    row = db.scalar(select(CalendarToken).where(CalendarToken.user_id == user.id))
    if row is not None:
        row.revoked_at = datetime.now(UTC)
        db.commit()
    return {"ok": True}


@app.get("/api/calendar/{token}.ics")
def calendar_feed(token: str, db: Session = Depends(get_session)):
    # Deliberately NOT behind require_user — calendar apps subscribe by URL,
    # they can't do cookie/session login. The token itself is the auth; a
    # leaked URL is revoked via DELETE /api/me/calendar-token, not a
    # password change.
    row = db.scalar(select(CalendarToken).where(CalendarToken.token == token, CalendarToken.revoked_at.is_(None)))
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown or revoked calendar link")
    bookings = db.scalars(select(Booking).where(Booking.educator_id == row.user_id)).all()
    events = []
    for b in bookings:
        room = db.get(Room, b.room_id)
        client = db.get(Client, b.client_id)
        events.append((b, room.name if room else "?", _client_label(client) if client else "?"))
    return PlainTextResponse(ical.render_ics(events), media_type="text/calendar")


# --- SPA serving ------------------------------------------------------
_DIST = os.path.join(os.path.dirname(__file__), "web", "dist")

if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.middleware("http")
    async def _asset_cache_headers(request, call_next):
        response = await call_next(request)
        # Vite content-hashes everything under /assets, so those may be
        # cached forever; index.html must NOT be — a home-screen PWA that
        # caches it keeps referencing old CSS/JS across deploys (the iOS
        # date-box fix appeared "not deployed" for exactly this reason).
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/")
    def _index():
        return FileResponse(os.path.join(_DIST, "index.html"))

    @app.get("/{full_path:path}")
    def _spa(full_path: str):
        candidate = os.path.join(_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_DIST, "index.html"))
else:
    @app.get("/")
    def _no_build():
        return JSONResponse(
            {"status": "backend up — React build not present; run the Vite dev server"},
        )
