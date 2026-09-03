"""Billing tests: which bookings are billable, price-at-session-date
(not today's price), sequential invoice numbering, and the admin API
around the billing run + issue."""
from __future__ import annotations

from datetime import date, datetime, timedelta, UTC


def _setup_priced_booking(admin_client, booking_env, *, status: str, client_price_cents: int, local_date: date, charge_waived: bool = False):
    from sqlalchemy import select
    from l360 import booking_logic
    from datetime import time as time_cls
    from l360.db import session_scope
    from l360.models import Booking, ServiceType

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
        booking = Booking(
            room_id=booking_env["room_id"], educator_id=booking_env["educator_id"],
            client_id=booking_env["client_id"], service_type_id=service_type.id,
            client_price_cents=service_type.client_price_cents, tutor_payment_cents=service_type.tutor_payment_cents,
            start_utc=start_utc, duration_minutes=60, status=status, created_by=1,
            charge_waived=charge_waived,
        )
        db.add(booking)
        db.flush()
        return booking.id


def test_billing_run_creates_invoice_for_billable_bookings(admin_client, booking_env):
    _setup_priced_booking(admin_client, booking_env, status="completed", client_price_cents=3000, local_date=date(2026, 5, 10))

    r = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["created"]) == 1
    invoice = body["created"][0]
    assert invoice["total_cents"] == 3000
    assert invoice["status"] == "draft"
    assert invoice["number"] is None  # not issued yet


def test_billing_run_skips_client_with_nothing_billable(admin_client, booking_env):
    r = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == []
    assert booking_env["client_id"] in body["skipped_clients"]


def test_past_confirmed_booking_bills_automatically(admin_client, booking_env):
    # Delivered-by-default (Fran, 03/09/2026): a past session nobody touched
    # is billable with no marking step at all.
    _setup_priced_booking(admin_client, booking_env, status="confirmed", client_price_cents=3000, local_date=date(2026, 5, 10))
    r = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    assert r.status_code == 200, r.text
    assert len(r.json()["created"]) == 1
    assert r.json()["created"][0]["total_cents"] == 3000


def test_waived_charges_are_not_billable(admin_client, booking_env):
    # The educator waived the fee — a waived no-show or late cancel bills
    # nothing, whatever its status says.
    _setup_priced_booking(admin_client, booking_env, status="no_show", client_price_cents=3000, local_date=date(2026, 5, 10), charge_waived=True)
    _setup_priced_booking(admin_client, booking_env, status="cancelled_late", client_price_cents=3000, local_date=date(2026, 5, 12), charge_waived=True)
    r = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    assert r.status_code == 200
    assert r.json()["created"] == []
    assert booking_env["client_id"] in r.json()["skipped_clients"]


def test_confirmed_booking_is_not_billable(admin_client, booking_env):
    # A future confirmed booking (not yet completed/cancelled/no-show).
    admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"], "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "service_type_id": booking_env["service_type_id"],
        "start_utc": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
        "duration_minutes": 60,
    })
    r = admin_client.post("/api/admin/billing/run", json={
        "period_start": str((datetime.now(UTC) + timedelta(days=55)).date()),
        "period_end": str((datetime.now(UTC) + timedelta(days=65)).date()),
    })
    assert r.json()["created"] == []


def test_billing_run_is_idempotent_no_double_billing(admin_client, booking_env):
    _setup_priced_booking(admin_client, booking_env, status="completed", client_price_cents=3000, local_date=date(2026, 5, 10))
    r1 = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    assert len(r1.json()["created"]) == 1

    # Running again for the same period: the booking is already on an
    # invoice line, so nothing new to bill.
    r2 = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    assert r2.json()["created"] == []


def test_price_used_is_locked_in_at_booking_time_not_todays(admin_client, booking_env):
    # The L360 price list (service types) is a flat, admin-editable table
    # with no valid_from versioning like the old level+duration price list
    # had — so the booking itself locks in the price at booking time
    # (Booking.client_price_cents), and billing must keep using that even
    # if the service type's price changes before the session is billed.
    from l360 import booking_logic
    from datetime import time as time_cls

    start_utc = booking_logic.local_to_utc(date(2026, 5, 10), time_cls(10, 0))
    r = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "service_type_id": booking_env["service_type_id"],
        "start_utc": start_utc.isoformat(),
        "duration_minutes": 60,
    })
    booking_id = r.json()["id"]
    assert r.json()["client_price_cents"] == 3500  # the service type's price at booking time

    # Raise the price after booking but before the session is billed.
    admin_client.put(f"/api/admin/service-types/{booking_env['service_type_id']}", json={
        "name": "Test Session", "category": "session",
        "client_price_cents": 5000, "tutor_payment_cents": 4000,
    })

    from l360.db import session_scope
    from l360.models import Booking
    with session_scope() as db:
        db.get(Booking, booking_id).status = "completed"

    r = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    assert r.json()["created"][0]["total_cents"] == 3500  # still the price at booking time, not 5000


def test_issue_invoice_assigns_sequential_numbers(admin_client, booking_env):
    _setup_priced_booking(admin_client, booking_env, status="completed", client_price_cents=3000, local_date=date(2026, 5, 10))
    _setup_priced_booking(admin_client, booking_env, status="completed", client_price_cents=4000, local_date=date(2026, 6, 10))

    run1 = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"}).json()
    run2 = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-06-01", "period_end": "2026-06-30"}).json()

    inv1 = admin_client.post(f"/api/admin/invoices/{run1['created'][0]['id']}/issue").json()
    inv2 = admin_client.post(f"/api/admin/invoices/{run2['created'][0]['id']}/issue").json()

    assert inv1["number"].startswith("L360-")
    assert inv1["status"] == "issued"
    assert inv1["number"] != inv2["number"]
    n1 = int(inv1["number"].rsplit("-", 1)[1])
    n2 = int(inv2["number"].rsplit("-", 1)[1])
    assert n2 == n1 + 1


def test_cannot_issue_already_issued_invoice(admin_client, booking_env):
    _setup_priced_booking(admin_client, booking_env, status="completed", client_price_cents=3000, local_date=date(2026, 5, 10))
    run = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"}).json()
    invoice_id = run["created"][0]["id"]
    assert admin_client.post(f"/api/admin/invoices/{invoice_id}/issue").status_code == 200
    r = admin_client.post(f"/api/admin/invoices/{invoice_id}/issue")
    assert r.status_code == 409


def test_invoice_detail_has_lines(admin_client, booking_env):
    _setup_priced_booking(admin_client, booking_env, status="completed", client_price_cents=3000, local_date=date(2026, 5, 10))
    run = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"}).json()
    invoice_id = run["created"][0]["id"]
    detail = admin_client.get(f"/api/admin/invoices/{invoice_id}").json()
    assert len(detail["lines"]) == 1
    assert detail["lines"][0]["amount_cents"] == 3000


def test_late_cancel_and_no_show_are_billable(admin_client, booking_env):
    _setup_priced_booking(admin_client, booking_env, status="cancelled_late", client_price_cents=3000, local_date=date(2026, 5, 10))
    _setup_priced_booking(admin_client, booking_env, status="no_show", client_price_cents=3000, local_date=date(2026, 5, 15))
    r = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    assert r.json()["created"][0]["total_cents"] == 6000


def test_free_cancel_is_not_billable(admin_client, booking_env):
    _setup_priced_booking(admin_client, booking_env, status="cancelled", client_price_cents=3000, local_date=date(2026, 5, 10))
    r = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    assert r.json()["created"] == []


def test_educator_cannot_access_billing(booking_env, educator_client):
    r = educator_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    assert r.status_code == 403


def test_invoice_settings_and_pdf(admin_client, monkeypatch):
    """Invoice template settings roundtrip + the PDF endpoints."""
    from l360 import invoice_pdf

    r = admin_client.put("/api/admin/invoice-settings", json={
        "name": "Learning 360 Foundation",
        "address": "Line 1\nLine 2",
        "vat": "VAT No: TEST",
        "bank": "Bank: Test\nIBAN: MT00",
        "contact": "test@example.org",
        "footer": "Payment due in 14 days.",
    })
    assert r.status_code == 200
    assert r.json()["vat"] == "VAT No: TEST"
    assert invoice_pdf.letterhead()["invoice_vat"] == "VAT No: TEST"

    r = admin_client.get("/api/admin/invoice-settings/sample-pdf")
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"


def test_invoice_line_carries_educator_and_pdf_downloads(admin_client, booking_env):
    _setup_priced_booking(admin_client, booking_env, status="completed", client_price_cents=3000, local_date=date(2026, 5, 12))
    r = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    invoice = r.json()["created"][0]

    detail = admin_client.get(f"/api/admin/invoices/{invoice['id']}").json()
    # The booking_env educator delivers the session — their name goes on the line.
    assert "Booking Educator" in detail["lines"][0]["description"]
    # Internal statuses never leak onto invoice lines.
    assert "completed" not in detail["lines"][0]["description"]

    r = admin_client.get(f"/api/admin/invoices/{invoice['id']}/pdf")
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"
    assert "DRAFT" in r.headers["content-disposition"]


def test_invoice_now_is_per_session_and_locks(admin_client, booking_env):
    """Confirm-flow "Send invoice now": ONE invoice for THAT session only
    (Simon 03/09); repeat refuses; the monthly run still picks up the
    family's other unsent sessions."""
    b1 = _setup_priced_booking(admin_client, booking_env, status="confirmed", client_price_cents=3000, local_date=date(2026, 8, 20))
    b2 = _setup_priced_booking(admin_client, booking_env, status="no_show", client_price_cents=4000, local_date=date(2026, 8, 25))
    waived = _setup_priced_booking(admin_client, booking_env, status="no_show", client_price_cents=4000, local_date=date(2026, 8, 26), charge_waived=True)

    ed = booking_env["educator_client"]
    r = ed.post(f"/api/bookings/{b1}/invoice-now")
    assert r.status_code == 200, r.text
    inv = r.json()
    assert inv["status"] == "issued"
    assert inv["number"] is not None
    assert inv["total_cents"] == 3000  # just b1 — not the no-show, not the waived one

    # b1 locked now — repeat refuses; b2 is untouched and still amendable.
    assert ed.post(f"/api/bookings/{b1}/invoice-now").status_code == 409
    assert ed.get(f"/api/bookings/{b2}").json()["invoiced"] is False
    # The waived no-show is not billable via invoice-now.
    assert ed.post(f"/api/bookings/{waived}/invoice-now").status_code == 409

    # Monthly safety-net run picks up the remaining charged no-show only.
    r = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-08-01", "period_end": "2026-08-31"})
    created = r.json()["created"]
    assert len(created) == 1
    assert created[0]["total_cents"] == 4000


def test_invoice_now_requires_assigned_educator(admin_client, booking_env):
    from starlette.testclient import TestClient
    from l360.api import app

    b1 = _setup_priced_booking(admin_client, booking_env, status="confirmed", client_price_cents=3000, local_date=date(2026, 8, 20))
    # A second, UNRELATED educator (the educator_client fixture can't be
    # combined with booking_env — both create a "Junior" level).
    level = admin_client.post("/api/admin/educator-levels", json={"name": "Senior"}).json()
    admin_client.post("/api/admin/users", json={
        "email": "other.ed@example.com", "full_name": "Other Ed",
        "role": "educator", "level_id": level["id"], "password": "otherpass1234",
    })
    other = TestClient(app)
    assert other.post("/api/login", json={"email": "other.ed@example.com", "password": "otherpass1234"}).status_code == 200
    assert other.post(f"/api/bookings/{b1}/invoice-now").status_code == 403
