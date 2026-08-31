"""Finance: client statements, educator summaries, utilisation report.

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


# --- statements / reports -------------------------------------------------
@router.get("/api/admin/statements/client/{client_id}", response_model=ClientStatementOut)
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


@router.get("/api/statements/educator/{educator_id}/summary", response_model=EducatorSummaryOut)
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


@router.get("/api/admin/reports/utilisation", response_model=list[RoomUtilisationOut])
def admin_utilisation_report(
    period_start: date_cls,
    period_end: date_cls,
    db: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    rows = statements_logic.utilisation_by_room(db, period_start=period_start, period_end=period_end)
    return [RoomUtilisationOut(**vars(r)) for r in rows]


