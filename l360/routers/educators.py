"""Educator onboarding: admin, internal checklist, contract, public form.

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


# --- educator onboarding ----------------------------------------------------
def _educator_onboarding_out(form: EducatorOnboardingForm) -> EducatorOnboardingAdminOut:
    return EducatorOnboardingAdminOut(
        id=form.id, user_id=form.user_id, status=form.status, source=form.source,
        link=educator_onboarding.form_link(form), sent_at=form.sent_at,
        submitted_at=form.submitted_at, signature_name=form.signature_name,
        signed_date=form.signed_date, answers=form.answers, internal=form.internal,
    )


@router.get("/api/admin/users/{user_id}/onboarding", response_model=EducatorOnboardingAdminOut | None)
def admin_get_educator_onboarding(user_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="Not found")
    form = db.scalar(select(EducatorOnboardingForm).where(EducatorOnboardingForm.user_id == user_id))
    return _educator_onboarding_out(form) if form else None


@router.post("/api/admin/users/{user_id}/onboarding/send", response_model=EducatorOnboardingAdminOut)
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



@router.put("/api/admin/users/{user_id}/onboarding/checklist", response_model=EducatorOnboardingAdminOut)
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



@router.get("/api/admin/users/{user_id}/onboarding/contract")
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


@router.get("/api/educator-onboarding/{token}", response_model=EducatorOnboardingPrefillOut)
def get_educator_onboarding(token: str, db: Session = Depends(get_session)):
    form, user = _educator_form_by_token(db, token)
    return EducatorOnboardingPrefillOut(status=form.status, full_name=user.full_name, email=user.email)


@router.post("/api/educator-onboarding/{token}")
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


