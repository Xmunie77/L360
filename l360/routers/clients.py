"""Learners: admin CRUD, onboarding admin, public onboarding form.

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


# --- admin: clients ---------------------------------------------------
def _client_out(row: Client, status: str | None) -> ClientOut:
    out = ClientOut.model_validate(row, from_attributes=True)
    out.onboarding_status = status
    return out


def _onboarding_status(db: Session, client_id: int) -> str | None:
    form = db.scalar(select(OnboardingForm).where(OnboardingForm.client_id == client_id))
    return form.status if form else None


@router.get("/api/admin/clients", response_model=list[ClientOut])
def admin_list_clients(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    rows = db.scalars(select(Client).order_by(Client.guardian_surname, Client.guardian_first_name)).all()
    statuses = {f.client_id: f.status for f in db.scalars(select(OnboardingForm)).all()}
    return [_client_out(r, statuses.get(r.id)) for r in rows]


@router.get("/api/admin/clients/{client_id}", response_model=ClientOut)
def admin_get_client(client_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    row = db.get(Client, client_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _client_out(row, _onboarding_status(db, row.id))


@router.post("/api/admin/clients", response_model=ClientOut)
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


@router.put("/api/admin/clients/{client_id}", response_model=ClientOut)
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


@router.get("/api/admin/clients/{client_id}/onboarding", response_model=OnboardingAdminOut | None)
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


@router.post("/api/admin/clients/{client_id}/onboarding/send", response_model=OnboardingAdminOut)
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





# --- public onboarding questionnaire ---------------------------------------
def _form_by_token(db: Session, token: str) -> tuple[OnboardingForm, Client]:
    # Deliberately NOT behind require_user — the guardian has no account.
    # The unguessable token is the auth, same pattern as the iCal feed.
    form = db.scalar(select(OnboardingForm).where(OnboardingForm.token == token))
    client = db.get(Client, form.client_id) if form else None
    if form is None or client is None or not client.active:
        raise HTTPException(status_code=404, detail="Unknown or expired onboarding link")
    return form, client


@router.get("/api/onboarding/{token}", response_model=OnboardingPrefillOut)
def get_onboarding(token: str, db: Session = Depends(get_session)):
    form, client = _form_by_token(db, token)
    return OnboardingPrefillOut(
        status=form.status,
        **{f: getattr(client, f) for f in onboarding.CLIENT_FIELDS},
    )


@router.post("/api/onboarding/{token}")
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


