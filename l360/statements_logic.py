"""Client statements, educator monthly pay summaries, and room-utilisation
reporting. All read-only aggregations over existing invoice/payment/
booking data — nothing here writes anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from l360.billing_logic import BILLABLE_STATUSES, price_for
from l360.booking_logic import utc_to_local
from l360.models import Booking, Client, Invoice, Payment, Room, User


def _naive_utc_bound(d: date, end_of_day: bool = False) -> datetime:
    t = time(23, 59, 59) if end_of_day else time(0, 0)
    return datetime.combine(d, t, tzinfo=UTC)


@dataclass
class StatementInvoiceLine:
    id: int
    number: str | None
    status: str
    total_cents: int
    issued_at: datetime | None


@dataclass
class StatementPaymentLine:
    id: int
    amount_cents: int
    method: str
    received_at: datetime


@dataclass
class ClientStatement:
    client_id: int
    period_start: date
    period_end: date
    opening_balance_cents: int
    invoices: list[StatementInvoiceLine] = field(default_factory=list)
    payments: list[StatementPaymentLine] = field(default_factory=list)
    closing_balance_cents: int = 0


def client_statement(db: Session, *, client_id: int, period_start: date, period_end: date) -> ClientStatement:
    period_start_dt = _naive_utc_bound(period_start)
    period_end_dt = _naive_utc_bound(period_end, end_of_day=True)

    all_invoices = db.scalars(
        select(Invoice).where(Invoice.client_id == client_id, Invoice.status != "draft")
    ).all()
    invoice_ids = {i.id for i in all_invoices}
    all_payments = (
        db.scalars(select(Payment).where(Payment.invoice_id.in_(invoice_ids))).all() if invoice_ids else []
    )

    billed_before = sum(i.total_cents for i in all_invoices if i.issued_at and i.issued_at < period_start_dt)
    paid_before = sum(p.amount_cents for p in all_payments if p.received_at < period_start_dt)
    opening_balance = billed_before - paid_before

    in_period_invoices = [
        i for i in all_invoices if i.issued_at and period_start_dt <= i.issued_at <= period_end_dt
    ]
    in_period_payments = [p for p in all_payments if period_start_dt <= p.received_at <= period_end_dt]

    billed_in_period = sum(i.total_cents for i in in_period_invoices)
    paid_in_period = sum(p.amount_cents for p in in_period_payments)

    return ClientStatement(
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        opening_balance_cents=opening_balance,
        invoices=[
            StatementInvoiceLine(id=i.id, number=i.number, status=i.status, total_cents=i.total_cents, issued_at=i.issued_at)
            for i in sorted(in_period_invoices, key=lambda x: x.issued_at)
        ],
        payments=[
            StatementPaymentLine(id=p.id, amount_cents=p.amount_cents, method=p.method, received_at=p.received_at)
            for p in sorted(in_period_payments, key=lambda x: x.received_at)
        ],
        closing_balance_cents=opening_balance + billed_in_period - paid_in_period,
    )


@dataclass
class SummarySessionLine:
    booking_id: int
    local_date: date
    client_label: str
    duration_minutes: int
    status: str
    rate_cents: int


@dataclass
class EducatorSummary:
    educator_id: int
    period_start: date
    period_end: date
    sessions: list[SummarySessionLine] = field(default_factory=list)
    total_payable_cents: int = 0


def educator_summary(db: Session, *, educator_id: int, period_start: date, period_end: date) -> EducatorSummary:
    educator = db.get(User, educator_id)
    period_start_dt = _naive_utc_bound(period_start) - timedelta(days=1)
    period_end_dt = _naive_utc_bound(period_end, end_of_day=True) + timedelta(days=1)

    candidates = db.scalars(
        select(Booking).where(
            Booking.educator_id == educator_id,
            Booking.status.in_(BILLABLE_STATUSES),
            Booking.start_utc >= period_start_dt,
            Booking.start_utc <= period_end_dt,
        )
    ).all()

    lines: list[SummarySessionLine] = []
    total = 0
    for b in candidates:
        local_date, _ = utc_to_local(b.start_utc)
        if not (period_start <= local_date <= period_end):
            continue
        client = db.get(Client, b.client_id)
        rate_cents = 0
        if educator and educator.level_id:
            entry = price_for(db, level_id=educator.level_id, duration_minutes=b.duration_minutes, as_of=local_date)
            rate_cents = entry.educator_rate_cents if entry else 0
        lines.append(SummarySessionLine(
            booking_id=b.id,
            local_date=local_date,
            client_label=client.guardian_name if client else "?",
            duration_minutes=b.duration_minutes,
            status=b.status,
            rate_cents=rate_cents,
        ))
        total += rate_cents

    lines.sort(key=lambda x: x.local_date)
    return EducatorSummary(
        educator_id=educator_id, period_start=period_start, period_end=period_end,
        sessions=lines, total_payable_cents=total,
    )


@dataclass
class RoomUtilisation:
    room_id: int
    room_name: str
    session_count: int
    booked_minutes: int


def utilisation_by_room(db: Session, *, period_start: date, period_end: date) -> list[RoomUtilisation]:
    period_start_dt = _naive_utc_bound(period_start)
    period_end_dt = _naive_utc_bound(period_end, end_of_day=True)
    bookings = db.scalars(
        select(Booking).where(
            Booking.status.in_(("confirmed", "completed")),
            Booking.start_utc >= period_start_dt,
            Booking.start_utc <= period_end_dt,
        )
    ).all()

    by_room: dict[int, list[Booking]] = {}
    for b in bookings:
        by_room.setdefault(b.room_id, []).append(b)

    out = []
    for room in db.scalars(select(Room).order_by(Room.sort_order)).all():
        rows = by_room.get(room.id, [])
        out.append(RoomUtilisation(
            room_id=room.id, room_name=room.name,
            session_count=len(rows), booked_minutes=sum(r.duration_minutes for r in rows),
        ))
    return out
