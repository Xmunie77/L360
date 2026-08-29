"""Notification tests: booking-event emails fire on create/move/cancel,
are idempotent per dedupe_key, and scheduled reminders/digest pick the
right bookings and never double-send."""
from __future__ import annotations

from datetime import datetime, time, timedelta, UTC

import pytest

from l360 import jobs, notify
from l360.booking_logic import local_to_utc, utc_to_local
from l360.models import NotificationLog


@pytest.fixture(autouse=True)
def _capture_emails(monkeypatch):
    """Redirect every send_email call into a list instead of hitting
    SMTP/logging, so tests can assert on what would have been sent."""
    sent = []
    monkeypatch.setattr(notify, "send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


def _future_start(hours_ahead: int) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours_ahead)).replace(microsecond=0).isoformat()


def _safe_future_start(hours_ahead: int) -> str:
    """Like _future_start, but nudged off local hour 23 — the one hour
    where a 60-minute session's start+duration crosses local midnight and
    gets correctly rejected by the app. Only ever moves earlier within the
    same calendar date, so it can't flip which side of a 24h boundary
    (relative to now) the result falls on."""
    dt_utc = datetime.now(UTC) + timedelta(hours=hours_ahead)
    local_date, local_time = utc_to_local(dt_utc)
    if local_time.hour == 23:
        local_time = local_time.replace(hour=21, minute=0, second=0, microsecond=0)
    return local_to_utc(local_date, local_time).isoformat()


def test_create_booking_sends_confirmation_to_educator_and_client(admin_client, booking_env, _capture_emails):
    _capture_emails.clear()  # drop the onboarding invite from booking_env's client creation
    r = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _future_start(48),
        "duration_minutes": 60,
    })
    assert r.status_code == 200
    assert len(_capture_emails) == 2  # educator + client (both have emails in booking_env)
    recipients = {to for to, _, _ in _capture_emails}
    assert recipients == {"booking.educator@example.com", "jane@example.com"}
    assert all("confirmed" in subject.lower() for _, subject, _ in _capture_emails)


def test_cancel_sends_cancel_notification(admin_client, booking_env, _capture_emails):
    booking = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _future_start(48),
        "duration_minutes": 60,
    }).json()
    _capture_emails.clear()

    admin_client.post(f"/api/bookings/{booking['id']}/cancel")
    assert len(_capture_emails) == 2
    assert all("cancelled" in subject.lower() for _, subject, _ in _capture_emails)


def test_move_sends_change_notification(admin_client, booking_env, _capture_emails):
    # Anchored to local mid-morning, not a pure now()+hours offset — the
    # move below adds another 5h on top, which can cross local midnight
    # (and get correctly rejected by the app) depending what time of day
    # the suite happens to run.
    start_dt = local_to_utc((datetime.now(UTC) + timedelta(days=2)).date(), time(9, 0))
    booking = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": start_dt.isoformat(),
        "duration_minutes": 60,
    }).json()
    _capture_emails.clear()

    admin_client.patch(f"/api/bookings/{booking['id']}", json={
        "start_utc": (start_dt + timedelta(hours=5)).isoformat(),
    })
    assert len(_capture_emails) == 2
    assert all("changed" in subject.lower() for _, subject, _ in _capture_emails)


def test_retrying_same_event_does_not_double_send(admin_client, booking_env, _capture_emails):
    """notify.send_once is idempotent per dedupe_key — calling it again
    with the exact same booking state must not send a second time."""
    from l360.db import session_scope
    from l360.models import Booking

    _capture_emails.clear()  # drop the onboarding invite from booking_env's client creation
    booking = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _future_start(48),
        "duration_minutes": 60,
    }).json()
    assert len(_capture_emails) == 2
    _capture_emails.clear()

    from l360 import notifications
    with session_scope() as db:
        row = db.get(Booking, booking["id"])
        notifications.notify_booking_event(db, row, "confirmation")  # exact same event again

    assert _capture_emails == []  # nothing new sent


def test_reminder_sent_only_within_24h_window(admin_client, booking_env, _capture_emails):
    from l360.db import session_scope

    # Just inside the window.
    admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _safe_future_start(20),
        "duration_minutes": 60,
    })
    # Outside the window.
    admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _safe_future_start(48),
        "duration_minutes": 60,
    })
    _capture_emails.clear()

    with session_scope() as db:
        sent_count = jobs.send_24h_reminders(db)
    assert sent_count == 2  # one booking, two recipients
    assert len(_capture_emails) == 2


def test_reminder_is_idempotent_across_runs(admin_client, booking_env, _capture_emails):
    from l360.db import session_scope

    # _safe_future_start, not _future_start — around local 11:00 a +12h slot
    # lands on local hour 23 and is correctly rejected for crossing midnight,
    # which made this test flaky depending on when the suite ran.
    r = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _safe_future_start(12),
        "duration_minutes": 60,
    })
    assert r.status_code == 200, r.text
    _capture_emails.clear()

    with session_scope() as db:
        first_run = jobs.send_24h_reminders(db)
    with session_scope() as db:
        second_run = jobs.send_24h_reminders(db)

    assert first_run == 2
    assert second_run == 0  # already reminded — no repeat
    assert len(_capture_emails) == 2


def test_daily_digest_groups_by_educator_and_skips_empty_days(admin_client, booking_env, _capture_emails):
    from l360.db import session_scope

    today_local = datetime.now(UTC).date()  # close enough for this synthetic test's own tz math
    start_utc = local_to_utc(today_local, time(10, 0))
    # Book far enough ahead in local time-of-day that "today" is unambiguous
    # regardless of the moment the test runs; skip if that slot's in the past.
    if start_utc <= datetime.now(UTC):
        pytest.skip("test run too late in the day for a same-day fixture slot")

    admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": start_utc.isoformat(),
        "duration_minutes": 60,
    })
    _capture_emails.clear()

    with session_scope() as db:
        sent = jobs.send_daily_digest(db, today=today_local)
    assert sent == 1
    assert _capture_emails[0][0] == "booking.educator@example.com"
    assert "today" in _capture_emails[0][1].lower()

    _capture_emails.clear()
    with session_scope() as db:
        sent_again = jobs.send_daily_digest(db, today=today_local)
    assert sent_again == 0  # idempotent


def test_notification_log_dedupe_key_is_actually_unique_in_db(admin_client, booking_env):
    """Defence in depth: confirm the DB constraint itself exists and
    rejects a duplicate insert, not just that our app-level check does."""
    from l360.db import session_scope
    from sqlalchemy.exc import IntegrityError

    with session_scope() as db:
        db.add(NotificationLog(kind="confirmation", dedupe_key="dupe-test-key"))
    with pytest.raises(IntegrityError):
        with session_scope() as db:
            db.add(NotificationLog(kind="confirmation", dedupe_key="dupe-test-key"))
