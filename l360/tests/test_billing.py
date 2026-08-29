"""Billing tests: which bookings are billable, price-at-session-date
(not today's price), sequential invoice numbering, and the admin API
around the billing run + issue."""
from __future__ import annotations

from datetime import date, datetime, timedelta, UTC


def _setup_priced_booking(admin_client, booking_env, *, status: str, client_price_cents: int, local_date: date):
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
            client_id=booking_env["client_id"], service_type_id=service_type.id, start_utc=start_utc,
            duration_minutes=60, status=status, created_by=1,
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


def test_price_used_is_the_service_types_current_price(admin_client, booking_env):
    # The L360 price list (service types) is a flat, admin-editable table —
    # unlike the old level+duration price list it replaced, there's no
    # valid_from versioning. Billing always uses whatever the service
    # type's price is *right now*, even for a booking dated in the past.
    from l360.db import session_scope
    from l360 import booking_logic
    from datetime import time as time_cls
    from l360.models import Booking, ServiceType

    with session_scope() as db:
        service_type = db.get(ServiceType, booking_env["service_type_id"])
        start_utc = booking_logic.local_to_utc(date(2026, 5, 10), time_cls(10, 0))
        db.add(Booking(
            room_id=booking_env["room_id"], educator_id=booking_env["educator_id"],
            client_id=booking_env["client_id"], service_type_id=service_type.id, start_utc=start_utc,
            duration_minutes=60, status="completed", created_by=1,
        ))

    # Raise the price after the session happened but before it's billed.
    admin_client.put(f"/api/admin/service-types/{booking_env['service_type_id']}", json={
        "name": "Test Session", "category": "session",
        "client_price_cents": 5000, "tutor_payment_cents": 4000,
    })

    r = admin_client.post("/api/admin/billing/run", json={"period_start": "2026-05-01", "period_end": "2026-05-31"})
    assert r.json()["created"][0]["total_cents"] == 5000  # the NEW price, not what it was at booking time


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
