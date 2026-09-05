"""End-to-end tests of l360.import_simplybook_bookings against dumps shaped
like SimplyBook's report/REST output (nested provider/service/client — the
shape confirmed against the live account) and the older flat shape."""
from __future__ import annotations

import json
from datetime import date, time

import pytest
from sqlalchemy import select

from l360.booking_logic import local_to_utc
from l360.db import session_scope
from l360.import_simplybook_bookings import cmd_import
from l360.models import Booking, Room


def _nested(sb_id, start, end, *, client_email="jane@example.com",
            provider_name="Booking Educator", service_name="Test Session Room 1 ",
            status="confirmed", duration=None):
    rec = {
        "id": sb_id,
        "code": f"code{sb_id}",
        "status": status,
        "start_datetime": start,
        "end_datetime": end,
        "provider": {"id": 5, "name": provider_name, "email": ""},
        "service": {"id": 2, "name": service_name},
        "client": {"id": 315, "name": "Someone", "email": client_email} if client_email else None,
    }
    if duration is not None:
        rec["duration"] = duration
    return rec


def _dump(tmp_path, bookings, providers=None):
    path = tmp_path / "dump.json"
    path.write_text(json.dumps({
        "exported_at": "2026-09-05T00:00:00+00:00",
        "company": "testco",
        "bookings": bookings,
        "services": [],
        "providers": providers or [],
        "booking_details": {},
    }))
    return str(path)


def _run(monkeypatch, dump_path, *extra):
    monkeypatch.setattr("sys.argv", [
        "import_simplybook_bookings", dump_path,
        "--default-room", "Test Room", "--created-by", "admin@example.com", *extra,
    ])
    cmd_import()


def test_import_maps_room_service_and_prices(booking_env, tmp_path, monkeypatch, capsys):
    with session_scope() as db:
        db.add(Room(name="Room 1"))

    # "Test Session Room 1" strips to booking_env's "Test Session" service
    # type (35.00 / 30.00) and lands in the "Room 1" room, not the default.
    dump = _dump(tmp_path, [
        _nested("77", "2027-03-01 10:00:00", "2027-03-01 11:30:00"),
    ])
    _run(monkeypatch, dump, "--commit")

    with session_scope() as db:
        booking = db.scalar(select(Booking))
        room_1 = db.scalar(select(Room).where(Room.name == "Room 1"))
        assert booking is not None
        assert booking.start_utc == local_to_utc(date(2027, 3, 1), time(10, 0))
        assert booking.duration_minutes == 90
        assert booking.room_id == room_1.id
        assert booking.client_id == booking_env["client_id"]
        assert booking.educator_id == booking_env["educator_id"]
        assert booking.service_type_id == booking_env["service_type_id"]
        assert booking.client_price_cents == 3500
        assert booking.tutor_payment_cents == 3000
        assert booking.status == "confirmed"
        assert "77" in (booking.notes or "")

    # Re-run: idempotent, nothing new.
    _run(monkeypatch, dump, "--commit")
    out = capsys.readouterr().out
    assert "1 already existed" in out
    with session_scope() as db:
        assert len(db.scalars(select(Booking)).all()) == 1


def test_no_room_number_falls_back_to_default(booking_env, tmp_path, monkeypatch):
    dump = _dump(tmp_path, [
        _nested(1, "2027-03-01 10:00:00", "2027-03-01 11:00:00",
                service_name="Educator II Home Session"),
    ])
    _run(monkeypatch, dump, "--commit")
    with session_scope() as db:
        booking = db.scalar(select(Booking))
        assert booking.room_id == booking_env["room_id"]  # "Test Room"
        assert booking.service_type_id is None  # no L360 match, no fallback given


def test_dry_run_writes_nothing(booking_env, tmp_path, monkeypatch, capsys):
    dump = _dump(tmp_path, [_nested(1, "2027-03-01 10:00:00", "2027-03-01 11:00:00")])
    _run(monkeypatch, dump)
    assert "Dry run" in capsys.readouterr().out
    with session_scope() as db:
        assert db.scalar(select(Booking)) is None


def test_unmatched_rows_are_reported_not_fatal(booking_env, tmp_path, monkeypatch, capsys):
    dump = _dump(tmp_path, [
        # Unknown client email → skipped, reported by simplybook ids only.
        _nested(1, "2027-03-01 10:00:00", "2027-03-01 11:00:00",
                client_email="stranger@example.com"),
        # Deleted client (null) → skipped.
        _nested(2, "2027-03-01 11:00:00", "2027-03-01 12:00:00", client_email=None),
        # Cancelled + good: still imported, as cancelled.
        _nested(3, "2027-03-02 09:00:00", "2027-03-02 10:00:00", status="canceled"),
    ])
    _run(monkeypatch, dump, "--commit")
    out = capsys.readouterr().out
    assert "client email not in L360" in out
    assert "stranger@example.com" not in out  # ids only in the log
    assert "no client on the record" in out
    with session_scope() as db:
        bookings = db.scalars(select(Booking)).all()
        assert len(bookings) == 1
        assert bookings[0].status == "cancelled"
        assert bookings[0].cancelled_at is not None


def test_flat_jsonrpc_shape_still_works(booking_env, tmp_path, monkeypatch):
    dump = _dump(
        tmp_path,
        [{"id": 9, "start_date_time": "2027-04-01 15:00:00",
          "end_date_time": "2027-04-01 16:00:00",
          "client_email": "jane@example.com", "unit_id": 5,
          "event": "Test Session"}],
        providers=[{"id": 5, "name": "Booking Educator"}],
    )
    _run(monkeypatch, dump, "--commit")
    with session_scope() as db:
        booking = db.scalar(select(Booking))
        assert booking is not None
        assert booking.service_type_id == booking_env["service_type_id"]


def test_past_status_flag(booking_env, tmp_path, monkeypatch):
    dump = _dump(tmp_path, [_nested(4, "2020-01-06 10:00:00", "2020-01-06 11:00:00")])
    _run(monkeypatch, dump, "--past-status", "completed", "--commit")
    with session_scope() as db:
        assert db.scalar(select(Booking)).status == "completed"


def test_missing_default_room_exits(booking_env, tmp_path, monkeypatch):
    dump = _dump(tmp_path, [])
    monkeypatch.setattr("sys.argv", [
        "import_simplybook_bookings", dump,
        "--default-room", "No Such Room", "--created-by", "admin@example.com",
    ])
    with pytest.raises(SystemExit):
        cmd_import()
