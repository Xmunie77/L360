"""End-to-end test of l360.import_simplybook_bookings against a dump file
shaped like SimplyBook's getBookings output."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from l360.booking_logic import local_to_utc
from l360.db import session_scope
from l360.import_simplybook_bookings import cmd_import
from l360.models import Booking


def _dump(tmp_path, bookings, providers=None, details=None):
    path = tmp_path / "dump.json"
    path.write_text(json.dumps({
        "exported_at": "2026-09-04T00:00:00+00:00",
        "company": "testco",
        "bookings": bookings,
        "services": [],
        "providers": providers or [],
        "booking_details": details or {},
    }))
    return str(path)


def _run(monkeypatch, dump_path, *extra):
    monkeypatch.setattr("sys.argv", [
        "import_simplybook_bookings", dump_path,
        "--room", "Test Room", "--created-by", "admin@example.com", *extra,
    ])
    cmd_import()


def test_import_creates_bookings(booking_env, tmp_path, monkeypatch, capsys):
    dump = _dump(tmp_path, [{
        "id": "77",
        "start_date_time": "2027-03-01 10:00:00",
        "end_date_time": "2027-03-01 11:30:00",
        "client_email": "jane@example.com",
        "unit": "Booking Educator",
    }])
    _run(monkeypatch, dump, "--service-type", "Test Session", "--commit")

    with session_scope() as db:
        booking = db.scalar(select(Booking))
        assert booking is not None
        from datetime import date, time
        assert booking.start_utc == local_to_utc(date(2027, 3, 1), time(10, 0))
        assert booking.duration_minutes == 90
        assert booking.client_id == booking_env["client_id"]
        assert booking.educator_id == booking_env["educator_id"]
        assert booking.status == "confirmed"
        assert booking.client_price_cents == 3500
        assert "77" in (booking.notes or "")

    # Re-run: idempotent, nothing new.
    _run(monkeypatch, dump, "--commit")
    out = capsys.readouterr().out
    assert "1 already existed" in out
    with session_scope() as db:
        assert len(db.scalars(select(Booking)).all()) == 1


def test_dry_run_writes_nothing(booking_env, tmp_path, monkeypatch):
    dump = _dump(tmp_path, [{
        "id": 1,
        "start_date_time": "2027-03-01 10:00:00",
        "client_email": "jane@example.com",
        "unit": "Booking Educator",
    }])
    _run(monkeypatch, dump)
    with session_scope() as db:
        assert db.scalar(select(Booking)) is None


def test_unmatched_rows_are_reported_not_fatal(booking_env, tmp_path, monkeypatch, capsys):
    dump = _dump(tmp_path, [
        # Unknown client email → skipped with reason.
        {"id": 1, "start_date_time": "2027-03-01 10:00:00",
         "client_email": "stranger@example.com", "unit": "Booking Educator"},
        # No start key at all → skipped, keys listed.
        {"id": 2, "client_email": "jane@example.com", "unit": "Booking Educator"},
        # Good row: still imported despite the two above; provider resolved
        # via unit_id → providers table; cancelled flag honoured.
        {"id": 3, "start_date_time": "2027-03-02 09:00:00",
         "end_date_time": "2027-03-02 10:00:00",
         "client_email": "jane@example.com", "unit_id": 5, "is_canceled": "1"},
    ], providers=[{"id": 5, "name": "Booking Educator"}])
    _run(monkeypatch, dump, "--commit")
    out = capsys.readouterr().out
    assert "not in L360" in out
    assert "no start time" in out
    with session_scope() as db:
        bookings = db.scalars(select(Booking)).all()
        assert len(bookings) == 1
        assert bookings[0].status == "cancelled"
        assert bookings[0].cancelled_at is not None


def test_client_email_from_details(booking_env, tmp_path, monkeypatch):
    """The list row may lack an email; getBookingDetails output fills it."""
    dump = _dump(
        tmp_path,
        [{"id": "9", "start_date_time": "2027-04-01 15:00:00", "unit": "Booking Educator"}],
        details={"9": {"client_email": "jane@example.com"}},
    )
    _run(monkeypatch, dump, "--commit")
    with session_scope() as db:
        assert db.scalar(select(Booking)) is not None


def test_past_status_flag(booking_env, tmp_path, monkeypatch):
    dump = _dump(tmp_path, [{
        "id": 4, "start_date_time": "2020-01-06 10:00:00",
        "client_email": "jane@example.com", "unit": "Booking Educator",
    }])
    _run(monkeypatch, dump, "--past-status", "completed", "--commit")
    with session_scope() as db:
        assert db.scalar(select(Booking)).status == "completed"


def test_missing_room_exits(booking_env, tmp_path, monkeypatch):
    dump = _dump(tmp_path, [])
    monkeypatch.setattr("sys.argv", [
        "import_simplybook_bookings", dump,
        "--room", "No Such Room", "--created-by", "admin@example.com",
    ])
    with pytest.raises(SystemExit):
        cmd_import()
