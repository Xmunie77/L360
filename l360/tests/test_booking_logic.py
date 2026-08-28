"""Pure booking-logic tests: local<->UTC conversion across DST, weekly
recurrence expansion, and conflict detection — no HTTP layer involved."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, UTC

import pytest

from l360 import booking_logic
from l360.booking_logic import SlotError
from l360.models import Booking, FacilityHours


def test_local_to_utc_before_dst_spring_forward():
    # Malta is UTC+1 (CET) in March before the last-Sunday-of-March switch.
    dt = booking_logic.local_to_utc(date(2026, 3, 22), time(10, 0))
    assert dt == datetime(2026, 3, 22, 9, 0, tzinfo=UTC)


def test_local_to_utc_after_dst_spring_forward():
    # After 2026-03-29, Malta is UTC+2 (CEST) — same local wall-clock time
    # now maps to a different UTC instant. This is exactly the bug class
    # naive datetime arithmetic gets wrong.
    dt = booking_logic.local_to_utc(date(2026, 4, 5), time(10, 0))
    assert dt == datetime(2026, 4, 5, 8, 0, tzinfo=UTC)


def test_utc_to_local_roundtrip():
    original_date, original_time = date(2026, 6, 15), time(14, 30)
    utc_dt = booking_logic.local_to_utc(original_date, original_time)
    back_date, back_time = booking_logic.utc_to_local(utc_dt)
    assert (back_date, back_time) == (original_date, original_time)


def test_expand_weekly_dates_basic():
    # Tuesdays (weekday=1) from a Monday to three weeks later.
    dates = booking_logic.expand_weekly_dates(date(2026, 9, 7), date(2026, 9, 28), weekday=1)
    assert dates == [date(2026, 9, 8), date(2026, 9, 15), date(2026, 9, 22)]


def test_expand_weekly_dates_across_dst_boundary():
    # A weekly Tuesday series spanning the 29 Mar 2026 spring-forward.
    dates = booking_logic.expand_weekly_dates(date(2026, 3, 17), date(2026, 4, 7), weekday=1)
    assert dates == [date(2026, 3, 17), date(2026, 3, 24), date(2026, 3, 31), date(2026, 4, 7)]
    # Every occurrence still resolves to 10:00 local wall-clock time, but the
    # UTC instant it maps to shifts by an hour once CEST (UTC+2) takes over
    # from CET (UTC+1) — this is exactly what naive datetime math gets wrong.
    before_utc_hours = {booking_logic.local_to_utc(d, time(10, 0)).hour for d in dates[:2]}
    after_utc_hours = {booking_logic.local_to_utc(d, time(10, 0)).hour for d in dates[2:]}
    assert before_utc_hours == {9}  # CET: 10:00 local = 09:00 UTC
    assert after_utc_hours == {8}   # CEST: 10:00 local = 08:00 UTC


def test_expand_weekly_dates_empty_range_returns_empty():
    assert booking_logic.expand_weekly_dates(date(2026, 9, 10), date(2026, 9, 1), weekday=0) == []


def test_check_within_hours_rejects_outside_open_hours(client):
    from l360.db import session_scope
    with session_scope() as db:
        db.add(FacilityHours(weekday=0, open_time=time(9, 0), close_time=time(17, 0)))
    from l360.db import session_scope as ss
    with ss() as db:
        # Monday 2026-09-07 08:00 local is before the 09:00 open time.
        start_utc = booking_logic.local_to_utc(date(2026, 9, 7), time(8, 0))
        with pytest.raises(SlotError, match="Outside facility opening hours"):
            booking_logic.check_within_hours_and_open(db, room_id=1, start_utc=start_utc, duration_minutes=60)


def test_find_conflict_detects_room_overlap(client):
    from l360.db import session_scope
    start = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)
    with session_scope() as db:
        db.add(Booking(
            room_id=1, educator_id=1, client_id=1, start_utc=start,
            duration_minutes=60, status="confirmed", created_by=1,
        ))
    with session_scope() as db:
        # Overlapping window, same room, different educator.
        conflict = booking_logic.find_conflict(
            db, room_id=1, educator_id=2,
            start_utc=start + timedelta(minutes=30), duration_minutes=60,
        )
        assert conflict is not None

        # Back-to-back (starts exactly when the first ends) — no overlap.
        no_conflict = booking_logic.find_conflict(
            db, room_id=1, educator_id=2,
            start_utc=start + timedelta(minutes=60), duration_minutes=60,
        )
        assert no_conflict is None


def test_find_conflict_ignores_cancelled_bookings(client):
    from l360.db import session_scope
    start = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)
    with session_scope() as db:
        db.add(Booking(
            room_id=1, educator_id=1, client_id=1, start_utc=start,
            duration_minutes=60, status="cancelled", created_by=1,
        ))
    with session_scope() as db:
        conflict = booking_logic.find_conflict(
            db, room_id=1, educator_id=2, start_utc=start, duration_minutes=60,
        )
        assert conflict is None
