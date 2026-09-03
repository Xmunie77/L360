"""Billing computation: which bookings are billable, what they cost (the
price locked in on the booking at booking time — see Booking.client_price_
cents — not whatever the service type currently costs), draft-invoice
generation, and sequential invoice numbering at issue time.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, UTC
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from l360.booking_logic import utc_to_local
from l360.config import INVOICE_NUMBER_PREFIX, TIMEZONE
from l360.models import Booking, Invoice, InvoiceLine, ServiceType, User

# Exception states that are billable unless the educator waived the fee.
# Since 03/09/2026 (Fran's rule) a past `confirmed` booking is ALSO
# billable — delivered by default, no marking step; `completed` stays
# recognised for pre-existing data. Plain `cancelled` (in-time, free) and
# future `confirmed` are not billable.
BILLABLE_STATUSES = ("completed", "cancelled_late", "no_show")


def billable_filter(now_utc: datetime | None = None):
    """The ONE SQL filter that decides billability — shared by invoicing
    (below) and the educator pay summary (statements_logic) so the two can
    never disagree: delivered (past confirmed) or an exception status,
    minus waived charges."""
    now_utc = now_utc or datetime.now(UTC)
    return and_(
        or_(
            Booking.status.in_(BILLABLE_STATUSES),
            and_(Booking.status == "confirmed", Booking.start_utc <= now_utc),
        ),
        Booking.charge_waived == False,  # noqa: E712 — SQL expression, not Python bool
    )


def billable_bookings_for_client(db: Session, *, client_id: int, period_start: date, period_end: date) -> list[Booking]:
    """Bookings for this client in [period_start, period_end] (by local
    session date) that are billable and not already on any invoice line."""
    # select(InvoiceLine.booking_id) selects a single column, so .scalars()
    # already unwraps each row to that column's value — iterating gives
    # plain ints directly, not InvoiceLine-like objects with a .booking_id.
    already_invoiced = set(db.scalars(select(InvoiceLine.booking_id).where(InvoiceLine.booking_id.is_not(None))))
    period_start_utc = datetime.combine(period_start, datetime.min.time(), tzinfo=UTC) - timedelta(days=1)
    period_end_utc = datetime.combine(period_end, datetime.min.time(), tzinfo=UTC) + timedelta(days=1)
    candidates = db.scalars(
        select(Booking).where(
            Booking.client_id == client_id,
            billable_filter(),
            Booking.start_utc >= period_start_utc,
            Booking.start_utc <= period_end_utc,
        )
    ).all()
    out = []
    for b in candidates:
        if b.id in already_invoiced:
            continue
        local_date, _ = utc_to_local(b.start_utc)
        if period_start <= local_date <= period_end:
            out.append(b)
    return out


class BillingError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def generate_draft_invoice(
    db: Session, *, client_id: int, period_start: date, period_end: date, created_by: int
) -> Invoice:
    bookings = billable_bookings_for_client(db, client_id=client_id, period_start=period_start, period_end=period_end)
    if not bookings:
        raise BillingError("No billable sessions for this learner in the given period")

    invoice = Invoice(
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        status="draft",
        created_by=created_by,
    )
    db.add(invoice)
    db.flush()

    total = 0
    for b in bookings:
        # The price locked in at booking time, not whatever the service
        # type currently costs — see Booking.client_price_cents.
        unit_price = b.client_price_cents or 0
        service_type = db.get(ServiceType, b.service_type_id) if b.service_type_id else None
        name = service_type.name if service_type else "Session"
        educator = db.get(User, b.educator_id)
        educator_bit = f" — {educator.full_name}" if educator else ""
        # Parent-facing wording: a delivered session needs no suffix; a
        # billable miss is named plainly rather than by internal status.
        status_bit = {"no_show": " (missed session)", "cancelled_late": " (late cancellation)"}.get(b.status, "")
        local_date, _ = utc_to_local(b.start_utc)
        line = InvoiceLine(
            invoice_id=invoice.id,
            booking_id=b.id,
            description=f"{name} — {local_date.isoformat()}{educator_bit}{status_bit}",
            unit_price_cents=unit_price,
            quantity=1,
            amount_cents=unit_price,
        )
        db.add(line)
        total += unit_price

    invoice.total_cents = total
    db.commit()
    db.refresh(invoice)
    return invoice


def _next_invoice_number(db: Session, year: int) -> str:
    """Highest existing sequence + 1 (not count+1: counting breaks the
    moment any number in the year is missing or duplicated by a prefix
    change, whereas max+1 always moves forward). Collisions from concurrent
    issues are still caught by the unique constraint + retry in
    issue_invoice()."""
    existing = db.scalars(
        select(Invoice.number).where(
            Invoice.number.is_not(None), Invoice.number.like(f"{INVOICE_NUMBER_PREFIX}-{year}-%")
        )
    ).all()
    max_seq = 0
    for number in existing:
        tail = number.rsplit("-", 1)[-1]
        if tail.isdigit():
            max_seq = max(max_seq, int(tail))
    return f"{INVOICE_NUMBER_PREFIX}-{year}-{max_seq + 1:04d}"


def issue_invoice(db: Session, invoice: Invoice, *, due_in_days: int = 14) -> Invoice:
    if invoice.status != "draft":
        raise BillingError(f"Cannot issue a {invoice.status} invoice")

    now = datetime.now(UTC)
    # Invoice number year + due date follow the MALTA calendar — an invoice
    # issued 00:30 on 1 Jan Malta time is still 31 Dec in UTC.
    local_now = now.astimezone(ZoneInfo(TIMEZONE))
    year = local_now.year
    # Small retry loop: two concurrent issues in the same year could both
    # compute the same "next" number — the unique constraint on `number`
    # catches that and we just recompute and try again.
    for _ in range(5):
        candidate = _next_invoice_number(db, year)
        invoice.number = candidate
        invoice.status = "issued"
        invoice.issued_at = now
        invoice.due_date = (local_now + timedelta(days=due_in_days)).date()
        db.add(invoice)
        try:
            db.commit()
            db.refresh(invoice)
            return invoice
        except IntegrityError:
            db.rollback()
            db.refresh(invoice)
            continue
    raise BillingError("Could not allocate an invoice number — try again")
