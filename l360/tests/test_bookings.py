"""API-level booking tests: create/conflict/move/cancel, series creation,
cancellation-cutoff billing matrix, and role permissions."""
from __future__ import annotations

from datetime import datetime, time as time_cls, timedelta, UTC

from l360.booking_logic import local_to_utc


def _future_start(hours_ahead: int) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours_ahead)).replace(microsecond=0).isoformat()


def _safe_morning_start(days_ahead: int = 2):
    """A start time anchored to local mid-morning, days_ahead from today —
    unlike a pure now()+timedelta(hours=N) offset, this stays clear of
    local midnight even after a few hours' further offset is added on top
    (as the move tests do), regardless of what time of day the suite runs."""
    return local_to_utc((datetime.now(UTC) + timedelta(days=days_ahead)).date(), time_cls(9, 0))


def test_create_booking_and_list(admin_client, booking_env):
    start = _future_start(48)
    r = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": start,
        "duration_minutes": 60,
    })
    assert r.status_code == 200, r.text
    booking = r.json()
    assert booking["status"] == "confirmed"
    assert booking["room_name"] == "Test Room"
    assert booking["client_label"] == "Jane Doe (JD)"

    window_start = (datetime.now(UTC)).isoformat()
    window_end = (datetime.now(UTC) + timedelta(hours=72)).isoformat()
    r = admin_client.get("/api/bookings", params={"start": window_start, "end": window_end})
    assert any(b["id"] == booking["id"] for b in r.json())


def test_create_booking_room_conflict_rejected(admin_client, booking_env):
    start = _future_start(48)
    body = {
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": start,
        "duration_minutes": 60,
    }
    assert admin_client.post("/api/bookings", json=body).status_code == 200

    # Same room, overlapping time, different (nonexistent but irrelevant)
    # educator id — still rejected because the room is the conflict.
    conflict_body = dict(body, educator_id=99999)
    r = admin_client.post("/api/bookings", json=conflict_body)
    assert r.status_code == 409
    assert "booked" in r.json()["detail"].lower()


def test_create_booking_back_to_back_allowed(admin_client, booking_env):
    start_dt = datetime.now(UTC) + timedelta(hours=48)
    body = {
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": start_dt.isoformat(),
        "duration_minutes": 60,
    }
    assert admin_client.post("/api/bookings", json=body).status_code == 200

    back_to_back = dict(body, start_utc=(start_dt + timedelta(minutes=60)).isoformat())
    assert admin_client.post("/api/bookings", json=back_to_back).status_code == 200


def test_invalid_duration_rejected(admin_client, booking_env):
    r = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _future_start(48),
        "duration_minutes": 45,  # not one of 60/90/120
    })
    assert r.status_code == 422


def test_move_booking_success_and_conflict(admin_client, booking_env):
    start_dt = _safe_morning_start()
    booking = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": start_dt.isoformat(),
        "duration_minutes": 60,
    }).json()
    other = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": (start_dt + timedelta(hours=2)).isoformat(),
        "duration_minutes": 60,
    }).json()

    # Move the first booking to a clear slot — succeeds.
    r = admin_client.patch(f"/api/bookings/{booking['id']}", json={
        "start_utc": (start_dt + timedelta(hours=5)).isoformat(),
    })
    assert r.status_code == 200

    # Move it onto the second booking's slot — conflict.
    r = admin_client.patch(f"/api/bookings/{booking['id']}", json={
        "start_utc": other["start_utc"],
    })
    assert r.status_code == 409


def test_cancel_outside_cutoff_is_free(admin_client, booking_env):
    booking = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _future_start(48),  # well outside the 24h cutoff
        "duration_minutes": 60,
    }).json()
    r = admin_client.post(f"/api/bookings/{booking['id']}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_cancel_inside_cutoff_is_billable(admin_client, booking_env):
    booking = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _future_start(4),  # inside the 24h cutoff
        "duration_minutes": 60,
    }).json()
    r = admin_client.post(f"/api/bookings/{booking['id']}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled_late"


def test_cancel_already_cancelled_rejected(admin_client, booking_env):
    booking = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _future_start(48),
        "duration_minutes": 60,
    }).json()
    admin_client.post(f"/api/bookings/{booking['id']}/cancel")
    r = admin_client.post(f"/api/bookings/{booking['id']}/cancel")
    assert r.status_code == 409


def test_series_creates_weekly_occurrences(admin_client, booking_env):
    starts_on = (datetime.now(UTC) + timedelta(days=7)).date()
    ends_on = starts_on + timedelta(days=21)
    r = admin_client.post("/api/bookings/series", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "weekday": starts_on.weekday(),
        "local_time": "10:00:00",
        "duration_minutes": 60,
        "starts_on": str(starts_on),
        "ends_on": str(ends_on),
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["created"]) == 4
    assert body["skipped"] == []
    assert all(b["series_id"] == body["series_id"] for b in body["created"])


def test_series_skips_conflicting_occurrence(admin_client, booking_env):
    starts_on = (datetime.now(UTC) + timedelta(days=7)).date()
    ends_on = starts_on + timedelta(days=14)

    # Pre-book the second occurrence's exact slot directly.
    from l360 import booking_logic
    from datetime import time as time_cls
    second_occurrence = starts_on + timedelta(days=7)
    admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": booking_logic.local_to_utc(second_occurrence, time_cls(10, 0)).isoformat(),
        "duration_minutes": 60,
    })

    r = admin_client.post("/api/bookings/series", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "weekday": starts_on.weekday(),
        "local_time": "10:00:00",
        "duration_minutes": 60,
        "starts_on": str(starts_on),
        "ends_on": str(ends_on),
    })
    body = r.json()
    assert len(body["created"]) == 2  # 3 occurrences, 1 skipped
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["date"] == str(second_occurrence)


def test_educator_can_only_modify_own_booking(admin_client, booking_env):
    booking = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _future_start(48),
        "duration_minutes": 60,
    }).json()

    # The educator this booking belongs to CAN cancel it.
    r = booking_env["educator_client"].post(f"/api/bookings/{booking['id']}/cancel")
    assert r.status_code == 200


def test_other_educator_cannot_modify_booking(admin_client, booking_env, educator_client):
    booking = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _future_start(48),
        "duration_minutes": 60,
    }).json()

    # `educator_client` is a *different* educator than booking_env's — 403.
    r = educator_client.post(f"/api/bookings/{booking['id']}/cancel")
    assert r.status_code == 403


def test_outside_facility_hours_rejected(admin_client, booking_env):
    # Narrow the hours for booking_env's weekday down to a small window,
    # then request a slot outside it.
    from l360 import booking_logic
    from datetime import time as time_cls
    target_date = (datetime.now(UTC) + timedelta(days=14)).date()
    admin_client.put("/api/admin/facility-hours", json={
        "weekday": target_date.weekday(), "open_time": "09:00:00", "close_time": "10:00:00",
    })
    start_utc = booking_logic.local_to_utc(target_date, time_cls(11, 0))
    r = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": start_utc.isoformat(),
        "duration_minutes": 60,
    })
    assert r.status_code == 409
    assert "hours" in r.json()["detail"].lower()


def test_facility_closure_rejected(admin_client, booking_env):
    from l360 import booking_logic
    from datetime import time as time_cls
    target_date = (datetime.now(UTC) + timedelta(days=14)).date()
    admin_client.post("/api/admin/closures", json={"date": str(target_date), "reason": "Public holiday"})
    start_utc = booking_logic.local_to_utc(target_date, time_cls(10, 0))
    r = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": start_utc.isoformat(),
        "duration_minutes": 60,
    })
    assert r.status_code == 409
    assert "closed" in r.json()["detail"].lower()


def test_mark_status_requires_admin_and_past_booking(admin_client, booking_env):
    future_booking = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "start_utc": _future_start(48),
        "duration_minutes": 60,
    }).json()

    # Educator (non-admin) cannot mark status at all.
    r = booking_env["educator_client"].post(
        f"/api/bookings/{future_booking['id']}/status", json={"status": "no_show"}
    )
    assert r.status_code == 403

    # Admin cannot mark a future booking as completed/no-show yet.
    r = admin_client.post(f"/api/bookings/{future_booking['id']}/status", json={"status": "no_show"})
    assert r.status_code == 409
