"""Statement/summary/utilisation/iCal tests: opening+invoices-payments=
closing arithmetic, educator summary totals, utilisation counts, and the
token-gated calendar feed."""
from __future__ import annotations

from datetime import date, datetime, UTC


def _issue_invoice_for_client(admin_client, booking_env, *, client_price_cents: int, local_date: date):
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
            room_id=booking_env["room_id"], educator_id=booking_env["educator_id"], client_id=booking_env["client_id"],
            service_type_id=service_type.id, client_price_cents=service_type.client_price_cents,
            tutor_payment_cents=service_type.tutor_payment_cents, start_utc=start_utc, duration_minutes=60,
            status="completed", created_by=1,
        ))

    run = admin_client.post("/api/admin/billing/run", json={"period_start": str(local_date.replace(day=1)), "period_end": str(local_date)}).json()
    invoice_id = run["created"][0]["id"]
    admin_client.post(f"/api/admin/invoices/{invoice_id}/issue")

    # issue_invoice() stamps issued_at with the real current time (correct
    # production behaviour), but these tests want to assert statement
    # balances as of a specific historical period — so backdate issued_at
    # here to when the invoice would realistically have gone out (a few
    # days after the session), the way a real monthly billing run would.
    from l360.db import session_scope as ss
    from l360.models import Invoice
    with ss() as db:
        inv = db.get(Invoice, invoice_id)
        inv.issued_at = datetime.combine(local_date, datetime.min.time(), tzinfo=UTC)
        db.add(inv)
    return admin_client.get(f"/api/admin/invoices/{invoice_id}").json()


def test_statement_balance_arithmetic(admin_client, booking_env):
    invoice = _issue_invoice_for_client(admin_client, booking_env, client_price_cents=3000, local_date=date(2026, 5, 10))
    admin_client.post("/api/admin/payments/record", json={
        "invoice_id": invoice["id"], "amount_cents": 1000, "method": "cash", "received_by_id": booking_env["educator_id"],
        "received_at": datetime(2026, 5, 20, tzinfo=UTC).isoformat(),
    })

    r = admin_client.get(f"/api/admin/statements/client/{booking_env['client_id']}", params={
        "period_start": "2026-05-01", "period_end": "2026-05-31",
    })
    assert r.status_code == 200
    s = r.json()
    assert s["opening_balance_cents"] == 0
    billed = sum(i["total_cents"] for i in s["invoices"])
    paid = sum(p["amount_cents"] for p in s["payments"])
    assert s["closing_balance_cents"] == s["opening_balance_cents"] + billed - paid
    assert s["closing_balance_cents"] == 2000


def test_statement_opening_balance_carries_prior_period(admin_client, booking_env):
    # May: billed 3000, paid 1000 -> outstanding 2000 carries into June.
    invoice = _issue_invoice_for_client(admin_client, booking_env, client_price_cents=3000, local_date=date(2026, 5, 10))
    admin_client.post("/api/admin/payments/record", json={
        "invoice_id": invoice["id"], "amount_cents": 1000, "method": "cash", "received_by_id": booking_env["educator_id"],
        "received_at": datetime(2026, 5, 15, tzinfo=UTC).isoformat(),
    })
    r = admin_client.get(f"/api/admin/statements/client/{booking_env['client_id']}", params={
        "period_start": "2026-06-01", "period_end": "2026-06-30",
    })
    s = r.json()
    assert s["opening_balance_cents"] == 2000
    assert s["invoices"] == []  # nothing new issued in June
    assert s["closing_balance_cents"] == 2000


def test_educator_summary_totals_and_self_access(admin_client, booking_env):
    _issue_invoice_for_client(admin_client, booking_env, client_price_cents=3000, local_date=date(2026, 5, 10))

    r = admin_client.get(f"/api/statements/educator/{booking_env['educator_id']}/summary", params={
        "period_start": "2026-05-01", "period_end": "2026-05-31",
    })
    assert r.status_code == 200
    body = r.json()
    assert len(body["sessions"]) == 1
    assert body["total_payable_cents"] == 1500  # 3000 client price -> 1500 educator rate (// 2)

    # The educator themself can fetch their own summary.
    r_self = booking_env["educator_client"].get(f"/api/statements/educator/{booking_env['educator_id']}/summary", params={
        "period_start": "2026-05-01", "period_end": "2026-05-31",
    })
    assert r_self.status_code == 200


def test_educator_cannot_fetch_another_educators_summary(admin_client, booking_env, educator_client):
    r = educator_client.get(f"/api/statements/educator/{booking_env['educator_id']}/summary", params={
        "period_start": "2026-05-01", "period_end": "2026-05-31",
    })
    assert r.status_code == 403


def test_utilisation_report_counts_sessions(admin_client, booking_env):
    from datetime import time as time_cls, timedelta

    from l360.booking_logic import local_to_utc

    # Anchored to local mid-morning — a bare now()+3d starts this 90-minute
    # session across local midnight when the suite runs late evening, and
    # the unasserted create silently 409s (count 0).
    start = local_to_utc((datetime.now(UTC) + timedelta(days=3)).date(), time_cls(9, 0)).isoformat()
    r = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"], "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "service_type_id": booking_env["service_type_id"], "start_utc": start, "duration_minutes": 90,
    })
    assert r.status_code == 200, r.text
    window_start = datetime.now(UTC).date().isoformat()
    window_end = (datetime.now(UTC) + timedelta(days=7)).date().isoformat()
    r = admin_client.get("/api/admin/reports/utilisation", params={"period_start": window_start, "period_end": window_end})
    assert r.status_code == 200
    row = next(x for x in r.json() if x["room_id"] == booking_env["room_id"])
    assert row["session_count"] == 1
    assert row["booked_minutes"] == 90


def test_calendar_token_lifecycle_and_feed(booking_env):
    ec = booking_env["educator_client"]
    assert ec.get("/api/me/calendar-token").json() is None

    created = ec.post("/api/me/calendar-token").json()
    assert created["feed_path"].startswith("/api/calendar/")

    # The feed route itself doesn't require the session cookie — the token
    # in the URL is the auth. Fetching it with a client that has no login
    # at all proves that.
    from fastapi.testclient import TestClient
    from l360.api import app
    anon_client = TestClient(app)
    feed = anon_client.get(created["feed_path"])
    assert feed.status_code == 200
    assert "BEGIN:VCALENDAR" in feed.text
    assert feed.headers["content-type"].startswith("text/calendar")

    # Revoke, then the same URL 404s.
    ec.delete("/api/me/calendar-token")
    assert ec.get(created["feed_path"]).status_code == 404


def test_calendar_feed_unknown_token_404s(client):
    r = client.get("/api/calendar/not-a-real-token.ics")
    assert r.status_code == 404
