"""Pure/DB-light booking logic: local-time<->UTC conversion (DST-safe via
zoneinfo), weekly-series date expansion, facility-hours/closure checks, and
conflict detection. Kept separate from api.py so it's directly unit-testable.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, UTC
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from l360.config import TIMEZONE
from l360.models import Booking, FacilityClosure, FacilityHours, Room

# Only these statuses occupy a room/educator slot. Cancelled (any flavour)
# and no-show bookings free the slot for rebooking — the session isn't
# happening, even though a late-cancel/no-show may still be billable.
_ACTIVE_STATUSES = ("confirmed", "completed")

# Widest possible session length — used to narrow the conflict pre-filter.
_MAX_DURATION_MINUTES = 120


def local_to_utc(d: date, t: time, tz_name: str = TIMEZONE) -> datetime:
    """Convert a Europe/Malta wall-clock date+time to an aware UTC datetime.

    zoneinfo resolves the correct UTC offset for that specific date, so this
    is correct across DST transitions without any special-casing.
    """
    local_dt = datetime.combine(d, t, tzinfo=ZoneInfo(tz_name))
    return local_dt.astimezone(UTC)


def utc_to_local(dt: datetime, tz_name: str = TIMEZONE) -> tuple[date, time]:
    local_dt = dt.astimezone(ZoneInfo(tz_name))
    return local_dt.date(), local_dt.time()


def local_today(tz_name: str = TIMEZONE) -> date:
    """Today as a Malta calendar date. Never use bare date.today() for a
    business date — the servers run UTC, so between midnight and ~2am Malta
    that returns YESTERDAY (invoice dates, price-list lookups, contracts)."""
    return datetime.now(ZoneInfo(tz_name)).date()


def expand_weekly_dates(starts_on: date, ends_on: date, weekday: int, interval_weeks: int = 1) -> list[date]:
    """All dates in [starts_on, ends_on] falling on the given weekday
    (0=Monday .. 6=Sunday, matching date.weekday()), every `interval_weeks`
    weeks (1 = every week, 2 = fortnightly)."""
    if ends_on < starts_on:
        return []
    delta = (weekday - starts_on.weekday()) % 7
    d = starts_on + timedelta(days=delta)
    dates = []
    while d <= ends_on:
        dates.append(d)
        d += timedelta(days=7 * interval_weeks)
    return dates


class SlotError(Exception):
    """Raised when a requested slot is outside hours, on a closure, or
    conflicts with an existing booking. `reason` is a short, user-facing
    string."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def check_within_hours_and_open(db: Session, room_id: int, start_utc: datetime, duration_minutes: int) -> None:
    local_date, local_start = utc_to_local(start_utc)
    local_end_dt = datetime.combine(local_date, local_start) + timedelta(minutes=duration_minutes)
    if local_end_dt.date() != local_date:
        raise SlotError("Session crosses midnight — not supported")
    local_end = local_end_dt.time()

    hours = db.scalar(select(FacilityHours).where(FacilityHours.weekday == local_date.weekday()))
    if hours is None:
        # Distinct message: "no hours set for Fridays" is an admin-config gap,
        # not a too-early/too-late slot — first hit live 03/09/2026 (Fran).
        day = local_date.strftime("%A")
        raise SlotError(f"No opening hours are set for {day}s — an admin can add them under Admin → Opening hours")
    if local_start < hours.open_time or local_end > hours.close_time:
        raise SlotError(
            f"Outside opening hours ({hours.open_time:%H:%M}–{hours.close_time:%H:%M} on {local_date.strftime('%A')}s)"
        )

    closure = db.scalar(
        select(FacilityClosure).where(
            FacilityClosure.date == local_date,
            or_(FacilityClosure.room_id == room_id, FacilityClosure.room_id.is_(None)),
        )
    )
    if closure is not None:
        raise SlotError(f"Facility closed: {closure.reason}")


def find_conflict(
    db: Session,
    *,
    room_id: int,
    educator_id: int,
    start_utc: datetime,
    duration_minutes: int,
    exclude_booking_id: int | None = None,
) -> Booking | None:
    end_utc = start_utc + timedelta(minutes=duration_minutes)
    window_start = start_utc - timedelta(minutes=_MAX_DURATION_MINUTES)
    q = select(Booking).where(
        Booking.status.in_(_ACTIVE_STATUSES),
        Booking.start_utc < end_utc,
        Booking.start_utc >= window_start,
        or_(Booking.room_id == room_id, Booking.educator_id == educator_id),
    )
    if exclude_booking_id is not None:
        q = q.where(Booking.id != exclude_booking_id)
    for row in db.scalars(q):
        row_end = row.start_utc + timedelta(minutes=row.duration_minutes)
        if row.start_utc < end_utc and row_end > start_utc:
            if row.room_id == room_id or row.educator_id == educator_id:
                return row
    return None


def facility_hours_configured(db: Session) -> bool:
    """Whether opening hours have been set for at least one weekday —
    with none set at all, every day gets skipped and every room looks
    unavailable regardless of bookings."""
    return db.scalar(select(FacilityHours.id)) is not None


def find_next_available_room(
    db: Session,
    *,
    duration_minutes: int = 60,
    now_utc: datetime | None = None,
    days_ahead: int = 14,
) -> tuple[Room, datetime] | None:
    """The earliest (room, start_utc) that's free for a session of the given
    length, scanning forward from now across facility hours/closures in
    30-minute steps. Rooms are tried in name order for a given slot, so an
    earlier slot always wins over an earlier room. None if nothing opens up
    within `days_ahead` days.

    Everything is prefetched in three queries (hours, closures, bookings)
    and the slot scan runs in memory — the previous version issued a
    closure + conflict query per room per 30-minute slot per day (P2 of the
    31/08/2026 review)."""
    now_utc = now_utc or datetime.now(UTC)
    rooms = db.scalars(select(Room).where(Room.active == True)).all()  # noqa: E712
    rooms = sorted(rooms, key=lambda r: r.name)
    if not rooms:
        return None

    hours_by_weekday = {h.weekday: h for h in db.scalars(select(FacilityHours))}
    if not hours_by_weekday:
        return None

    first_local_date, _ = utc_to_local(now_utc)
    last_local_date, _ = utc_to_local(now_utc + timedelta(days=days_ahead))
    closures = db.scalars(
        select(FacilityClosure).where(
            FacilityClosure.date >= first_local_date, FacilityClosure.date <= last_local_date
        )
    ).all()
    closed: set[tuple[date, int | None]] = {(c.date, c.room_id) for c in closures}

    horizon_end = now_utc + timedelta(days=days_ahead + 1)
    bookings = db.scalars(
        select(Booking).where(
            Booking.status.in_(_ACTIVE_STATUSES),
            Booking.start_utc >= now_utc - timedelta(minutes=_MAX_DURATION_MINUTES),
            Booking.start_utc < horizon_end,
        )
    ).all()
    busy_by_room: dict[int, list[tuple[datetime, datetime]]] = {}
    for b in bookings:
        busy_by_room.setdefault(b.room_id, []).append(
            (b.start_utc, b.start_utc + timedelta(minutes=b.duration_minutes))
        )

    for day_offset in range(days_ahead):
        local_date, _ = utc_to_local(now_utc + timedelta(days=day_offset))
        hours = hours_by_weekday.get(local_date.weekday())
        if hours is None or (local_date, None) in closed:
            continue

        t = hours.open_time
        while True:
            end_local = datetime.combine(local_date, t) + timedelta(minutes=duration_minutes)
            if end_local.date() != local_date or end_local.time() > hours.close_time:
                break
            start_utc = local_to_utc(local_date, t)
            if start_utc >= now_utc:
                slot_end = start_utc + timedelta(minutes=duration_minutes)
                for room in rooms:
                    if (local_date, room.id) in closed:
                        continue
                    if any(bs < slot_end and be > start_utc for bs, be in busy_by_room.get(room.id, ())):
                        continue
                    return room, start_utc
            next_dt = datetime.combine(local_date, t) + timedelta(minutes=30)
            if next_dt.date() != local_date:
                break
            t = next_dt.time()
    return None


def validate_slot(
    db: Session,
    *,
    room_id: int,
    educator_id: int,
    start_utc: datetime,
    duration_minutes: int,
    exclude_booking_id: int | None = None,
) -> None:
    """Raises SlotError if the slot can't be booked. Order: hours/closure
    first (cheap, no query needed beyond two small lookups), then conflicts."""
    check_within_hours_and_open(db, room_id, start_utc, duration_minutes)
    conflict = find_conflict(
        db,
        room_id=room_id,
        educator_id=educator_id,
        start_utc=start_utc,
        duration_minutes=duration_minutes,
        exclude_booking_id=exclude_booking_id,
    )
    if conflict is not None:
        what = "room" if conflict.room_id == room_id else "educator"
        raise SlotError(f"That {what} is already booked at this time")
