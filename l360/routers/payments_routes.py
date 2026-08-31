"""Payments: provider sync, matching, manual records.

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


# --- payments / reconciliation ---------------------------------------------
@router.post("/api/admin/payments/sync", response_model=SyncResultOut)
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


@router.get("/api/admin/payments/unmatched", response_model=list[BankTxnOut])
def admin_unmatched_txns(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    rows = db.scalars(
        select(BankTxn).where(BankTxn.payment_id.is_(None)).order_by(BankTxn.txn_date.desc())
    ).all()
    return rows


@router.post("/api/admin/payments/manual-match", response_model=PaymentOut)
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


@router.post("/api/admin/payments/record", response_model=PaymentOut)
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


