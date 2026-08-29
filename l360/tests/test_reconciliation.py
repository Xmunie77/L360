"""Reconciliation tests: reference matching, amount-fallback matching
(only when unambiguous), re-import idempotency, manual matching, and
manual payment recording. All against synthetic BankTxn/RawTxn data —
no real Revolut API involved."""
from __future__ import annotations

from datetime import date, datetime, UTC

from l360 import reconciliation
from l360.payments.provider import RawTxn


def _issued_invoice(admin_client, booking_env, *, client_price_cents: int, local_date: date):
    from l360.db import session_scope
    from l360.models import Booking, ServiceType
    import l360.booking_logic as booking_logic
    from datetime import time as time_cls
    from sqlalchemy import select

    with session_scope() as db:
        # Reuse an existing service type at this exact price if a prior call
        # in the same test already created one — ServiceType.name is unique.
        name = f"Test Session {client_price_cents}c"
        service_type = db.scalar(select(ServiceType).where(ServiceType.name == name))
        if service_type is None:
            service_type = ServiceType(
                name=name, category="session",
                client_price_cents=client_price_cents, tutor_payment_cents=client_price_cents // 2,
            )
            db.add(service_type)
            db.flush()
        start_utc = booking_logic.local_to_utc(local_date, time_cls(10, 0))
        db.add(Booking(
            room_id=booking_env["room_id"], educator_id=booking_env["educator_id"],
            client_id=booking_env["client_id"], service_type_id=service_type.id,
            client_price_cents=service_type.client_price_cents, tutor_payment_cents=service_type.tutor_payment_cents,
            start_utc=start_utc, duration_minutes=60, status="completed", created_by=1,
        ))

    period_start, period_end = local_date.replace(day=1), local_date
    run = admin_client.post("/api/admin/billing/run", json={"period_start": str(period_start), "period_end": str(period_end)}).json()
    invoice_id = run["created"][0]["id"]
    return admin_client.post(f"/api/admin/invoices/{invoice_id}/issue").json()


def test_import_transactions_is_idempotent(admin_client):
    from l360.db import session_scope

    txns = [RawTxn(external_id="tx1", txn_date=datetime.now(UTC), amount_cents=3000, currency="EUR", reference="ref", counterparty="Someone")]
    with session_scope() as db:
        first = reconciliation.import_transactions(db, txns)
        assert len(first) == 1
        second = reconciliation.import_transactions(db, txns)  # same external_id again
        assert len(second) == 0  # nothing new — already imported


def test_reference_match_wins_over_amount(admin_client, booking_env):
    invoice = _issued_invoice(admin_client, booking_env, client_price_cents=3000, local_date=date(2026, 5, 10))
    from l360.db import session_scope
    from l360.models import BankTxn

    with session_scope() as db:
        txn = BankTxn(external_id="tx-ref", txn_date=datetime.now(UTC), amount_cents=3000, currency="EUR", reference=f"Payment for {invoice['number']}", counterparty="Jane Doe")
        db.add(txn)
        db.flush()
        payment = reconciliation.try_match(db, txn)
        assert payment is not None
        assert payment.match_status == "auto"

    r = admin_client.get(f"/api/admin/invoices/{invoice['id']}")
    assert r.json()["status"] == "paid"
    assert r.json()["outstanding_cents"] == 0


def test_amount_fallback_match_when_reference_absent(admin_client, booking_env):
    _issued_invoice(admin_client, booking_env, client_price_cents=3000, local_date=date(2026, 5, 10))
    from l360.db import session_scope
    from l360.models import BankTxn

    with session_scope() as db:
        txn = BankTxn(external_id="tx-amount", txn_date=datetime.now(UTC), amount_cents=3000, currency="EUR", reference=None, counterparty="Jane Doe")
        db.add(txn)
        db.flush()
        payment = reconciliation.try_match(db, txn)
        assert payment is not None


def test_ambiguous_amount_left_unmatched(admin_client, booking_env):
    from l360.db import session_scope
    from l360.models import BankTxn

    # Two clients, two invoices, same amount — no reference to disambiguate.
    _issued_invoice(admin_client, booking_env, client_price_cents=3000, local_date=date(2026, 5, 10))

    second_client = admin_client.post(
        "/api/admin/clients",
        json={"guardian_first_name": "Second", "guardian_surname": "Parent", "email": "second@example.com"},
    ).json()
    with session_scope() as db:
        from l360.models import Booking, ServiceType
        import l360.booking_logic as booking_logic
        from datetime import time as time_cls
        from sqlalchemy import select
        # Same service type (and so the same price, 3000c) as the first
        # invoice — that's the whole point of this test: two invoices with
        # an identical amount and no reference to disambiguate them.
        service_type = db.scalar(select(ServiceType).where(ServiceType.name == "Test Session 3000c"))
        start_utc = booking_logic.local_to_utc(date(2026, 5, 12), time_cls(11, 0))
        db.add(Booking(
            room_id=booking_env["room_id"], educator_id=booking_env["educator_id"],
            client_id=second_client["id"], service_type_id=service_type.id,
            client_price_cents=service_type.client_price_cents, tutor_payment_cents=service_type.tutor_payment_cents,
            start_utc=start_utc, duration_minutes=60, status="completed", created_by=1,
        ))
    run2 = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"}).json()
    invoice2 = next(i for i in run2["created"] if i["client_id"] == second_client["id"])
    admin_client.post(f"/api/admin/invoices/{invoice2['id']}/issue")

    with session_scope() as db:
        txn = BankTxn(external_id="tx-ambiguous", txn_date=datetime.now(UTC), amount_cents=3000, currency="EUR", reference=None, counterparty="?")
        db.add(txn)
        db.flush()
        payment = reconciliation.try_match(db, txn)
        assert payment is None  # ambiguous — left for a human


def test_manual_match(admin_client, booking_env):
    invoice = _issued_invoice(admin_client, booking_env, client_price_cents=3000, local_date=date(2026, 5, 10))
    from l360.db import session_scope
    from l360.models import BankTxn

    with session_scope() as db:
        txn = BankTxn(external_id="tx-manual", txn_date=datetime.now(UTC), amount_cents=1500, currency="EUR", reference="unrelated text", counterparty="?")
        db.add(txn)
        db.flush()
        txn_id = txn.id

    r = admin_client.post("/api/admin/payments/manual-match", json={"bank_txn_id": txn_id, "invoice_id": invoice["id"]})
    assert r.status_code == 200
    assert r.json()["match_status"] == "manual"

    inv = admin_client.get(f"/api/admin/invoices/{invoice['id']}").json()
    assert inv["status"] == "partially_paid"
    assert inv["outstanding_cents"] == 1500


def test_manual_match_rejects_already_matched_txn(admin_client, booking_env):
    invoice = _issued_invoice(admin_client, booking_env, client_price_cents=3000, local_date=date(2026, 5, 10))
    from l360.db import session_scope
    from l360.models import BankTxn

    with session_scope() as db:
        txn = BankTxn(external_id="tx-double", txn_date=datetime.now(UTC), amount_cents=3000, currency="EUR")
        db.add(txn)
        db.flush()
        txn_id = txn.id

    admin_client.post("/api/admin/payments/manual-match", json={"bank_txn_id": txn_id, "invoice_id": invoice["id"]})
    r = admin_client.post("/api/admin/payments/manual-match", json={"bank_txn_id": txn_id, "invoice_id": invoice["id"]})
    assert r.status_code == 409


def test_record_manual_payment_cash(admin_client, booking_env):
    invoice = _issued_invoice(admin_client, booking_env, client_price_cents=3000, local_date=date(2026, 5, 10))
    r = admin_client.post("/api/admin/payments/record", json={
        "invoice_id": invoice["id"], "amount_cents": 3000, "method": "cash",
        "received_at": datetime.now(UTC).isoformat(),
    })
    assert r.status_code == 200
    assert r.json()["match_status"] == "manual"
    inv = admin_client.get(f"/api/admin/invoices/{invoice['id']}").json()
    assert inv["status"] == "paid"


def test_partial_payment_leaves_invoice_partially_paid(admin_client, booking_env):
    invoice = _issued_invoice(admin_client, booking_env, client_price_cents=3000, local_date=date(2026, 5, 10))
    admin_client.post("/api/admin/payments/record", json={
        "invoice_id": invoice["id"], "amount_cents": 1000, "method": "cash",
        "received_at": datetime.now(UTC).isoformat(),
    })
    inv = admin_client.get(f"/api/admin/invoices/{invoice['id']}").json()
    assert inv["status"] == "partially_paid"
    assert inv["outstanding_cents"] == 2000


def test_unmatched_endpoint_lists_only_unmatched(admin_client, booking_env):
    from l360.db import session_scope
    from l360.models import BankTxn

    with session_scope() as db:
        db.add(BankTxn(external_id="tx-loose", txn_date=datetime.now(UTC), amount_cents=999, currency="EUR"))

    r = admin_client.get("/api/admin/payments/unmatched")
    assert r.status_code == 200
    assert any(t["external_id"] == "tx-loose" for t in r.json())


def test_sync_without_configured_provider_returns_clear_error(admin_client):
    r = admin_client.post("/api/admin/payments/sync")
    assert r.status_code == 409
    assert "REVOLUT_API_TOKEN" in r.json()["detail"]
