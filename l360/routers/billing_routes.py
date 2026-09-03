"""Billing: runs, invoices, issue + PDF, invoice template settings.

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


# --- admin: invoice template settings + PDF --------------------------------
_INVOICE_KEY_MAP = {
    "name": "invoice_name", "address": "invoice_address", "vat": "invoice_vat",
    "bank": "invoice_bank", "contact": "invoice_contact", "footer": "invoice_footer",
}


@router.get("/api/admin/invoice-settings", response_model=InvoiceSettingsOut)
def admin_get_invoice_settings(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    head = invoice_pdf.letterhead()
    return InvoiceSettingsOut(**{field: head[key] for field, key in _INVOICE_KEY_MAP.items()})


@router.put("/api/admin/invoice-settings", response_model=InvoiceSettingsOut)
def admin_save_invoice_settings(
    body: InvoiceSettingsIn, db: Session = Depends(get_session), admin: User = Depends(require_admin)
):
    for field, key in _INVOICE_KEY_MAP.items():
        _upsert_setting(db, key, getattr(body, field).strip())
    db.commit()
    return admin_get_invoice_settings(db, admin)


@router.get("/api/admin/invoice-settings/sample-pdf")
def admin_sample_invoice_pdf(db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    """A dummy invoice rendered with the CURRENT letterhead — so template
    changes can be eyeballed without touching a real invoice."""
    data = invoice_pdf.InvoicePdfData(
        number="SAMPLE-0000",
        issue_date=booking_logic.local_today(),
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
    booking_ids = {line.booking_id for line in lines if line.booking_id}
    line_bookings = {b.id: b for b in db.scalars(select(Booking).where(Booking.id.in_(booking_ids)))} if booking_ids else {}
    educators = {u.id: u for u in db.scalars(select(User).where(User.id.in_({b.educator_id for b in line_bookings.values()})))} if line_bookings else {}
    pdf_lines = []
    for line in lines:
        desc = line.description
        # Lines generated before 30/08/2026 lack the educator name — add it
        # from the booking at render time so older invoices carry it too.
        if line.booking_id:
            b = line_bookings.get(line.booking_id)
            educator = educators.get(b.educator_id) if b else None
            if educator and educator.full_name not in desc:
                desc = f"{desc} — {educator.full_name}"
        pdf_lines.append(invoice_pdf.InvoiceLinePdf(desc, line.quantity, line.unit_price_cents, line.amount_cents))
    attn_names = [client.guardian_name] if client else []
    if client and client.guardian2_name:
        attn_names.append(client.guardian2_name)
    paid = inv.total_cents - reconciliation.outstanding_cents(db, inv)
    return invoice_pdf.InvoicePdfData(
        number=inv.number or "DRAFT",
        issue_date=booking_logic.utc_to_local(inv.issued_at or inv.created_at)[0],
        learner_name=(client.child_name or client.guardian_name) if client else "?",
        attn=" and ".join(attn_names),
        bill_address=client.address if client else None,
        lines=pdf_lines,
        total_cents=inv.total_cents,
        paid_cents=paid,
    )


@router.get("/api/admin/invoices/{invoice_id}/pdf")
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


@router.post("/api/admin/billing/run", response_model=BillingRunOut)
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


@router.get("/api/admin/invoices", response_model=list[InvoiceOut])
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


@router.get("/api/admin/invoices/{invoice_id}", response_model=InvoiceDetailOut)
def admin_get_invoice(invoice_id: int, db: Session = Depends(get_session), _admin: User = Depends(require_admin)):
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Not found")
    lines = db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)).all()
    base = _invoice_out(db, inv)
    return InvoiceDetailOut(**base.model_dump(), lines=[InvoiceLineOut.model_validate(l, from_attributes=True) for l in lines])


@router.post("/api/admin/invoices/{invoice_id}/issue", response_model=InvoiceOut)
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


