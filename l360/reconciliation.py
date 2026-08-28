"""Matches raw bank transactions to open invoices. Provider-agnostic — it
takes RawTxn (payments/provider.py), never anything Revolut-specific, so
it's fully testable against synthetic data without a live API.

Matching order: reference (the invoice number appearing in the
transaction's reference text) first, then — only if no reference match —
exact outstanding-amount match, and only when it identifies exactly ONE
open invoice. An ambiguous amount match is left unmatched for a human
rather than guessed at.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from l360.models import BankTxn, Invoice, Payment
from l360.payments.provider import RawTxn

_OPEN_STATUSES = ("issued", "partially_paid")


def import_transactions(db: Session, txns: list[RawTxn]) -> list[BankTxn]:
    """Insert new BankTxn rows, skipping any already imported (external_id
    is unique) — safe to call repeatedly with overlapping data."""
    existing_ids = set(db.scalars(select(BankTxn.external_id)))
    new_rows = []
    for t in txns:
        if t.external_id in existing_ids:
            continue
        row = BankTxn(
            external_id=t.external_id,
            txn_date=t.txn_date,
            amount_cents=t.amount_cents,
            currency=t.currency,
            reference=t.reference,
            counterparty=t.counterparty,
        )
        db.add(row)
        new_rows.append(row)
    db.commit()
    for row in new_rows:
        db.refresh(row)
    return new_rows


def outstanding_cents(db: Session, invoice: Invoice) -> int:
    paid = sum(p.amount_cents for p in db.scalars(select(Payment).where(Payment.invoice_id == invoice.id)))
    return invoice.total_cents - paid


def _update_invoice_status(db: Session, invoice: Invoice) -> None:
    invoice.status = "paid" if outstanding_cents(db, invoice) <= 0 else "partially_paid"
    db.add(invoice)


def try_match(db: Session, txn: BankTxn) -> Payment | None:
    if txn.payment_id is not None:
        return None  # already matched

    open_invoices = db.scalars(select(Invoice).where(Invoice.status.in_(_OPEN_STATUSES))).all()

    matched: Invoice | None = None
    if txn.reference:
        ref = txn.reference.upper()
        by_reference = [inv for inv in open_invoices if inv.number and inv.number.upper() in ref]
        if len(by_reference) == 1:
            matched = by_reference[0]

    if matched is None:
        by_amount = [inv for inv in open_invoices if outstanding_cents(db, inv) == txn.amount_cents]
        if len(by_amount) == 1:
            matched = by_amount[0]

    if matched is None:
        return None

    payment = Payment(
        invoice_id=matched.id,
        amount_cents=txn.amount_cents,
        method="revolut_transfer",
        external_ref=txn.external_id,
        received_at=txn.txn_date,
        match_status="auto",
    )
    db.add(payment)
    db.flush()
    txn.payment_id = payment.id
    _update_invoice_status(db, matched)
    db.commit()
    db.refresh(payment)
    return payment


def record_manual_payment(
    db: Session,
    *,
    invoice: Invoice,
    amount_cents: int,
    method: str,
    received_at: datetime,
    created_by: int,
    external_ref: str | None = None,
) -> Payment:
    payment = Payment(
        invoice_id=invoice.id,
        amount_cents=amount_cents,
        method=method,
        external_ref=external_ref,
        received_at=received_at,
        match_status="manual",
        created_by=created_by,
    )
    db.add(payment)
    db.flush()
    _update_invoice_status(db, invoice)
    db.commit()
    db.refresh(payment)
    return payment


def manual_match(db: Session, *, bank_txn: BankTxn, invoice: Invoice, created_by: int) -> Payment:
    if bank_txn.payment_id is not None:
        raise ValueError("Transaction already matched")
    payment = Payment(
        invoice_id=invoice.id,
        amount_cents=bank_txn.amount_cents,
        method="revolut_transfer",
        external_ref=bank_txn.external_id,
        received_at=bank_txn.txn_date,
        match_status="manual",
        created_by=created_by,
    )
    db.add(payment)
    db.flush()
    bank_txn.payment_id = payment.id
    _update_invoice_status(db, invoice)
    db.commit()
    db.refresh(payment)
    return payment
