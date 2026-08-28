"""Minimal iCalendar (RFC 5545) rendering for the read-only per-user feed.
Hand-rolled rather than a dependency: one VEVENT per booking is a small,
stable format that doesn't need a library.
"""
from __future__ import annotations

from datetime import timedelta

from l360.models import Booking

# Only these statuses are worth putting on a calendar — a cancelled or
# no-show session isn't something to show up as an appointment.
_VISIBLE_STATUSES = ("confirmed", "completed")


def _dt(dt) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def render_ics(events: list[tuple[Booking, str, str]]) -> str:
    """events: (booking, room_name, client_label) tuples."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Learning 360 Foundation//l360//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Learning 360\u00b0 sessions",
    ]
    for booking, room_name, client_label in events:
        if booking.status not in _VISIBLE_STATUSES:
            continue
        end = booking.start_utc + timedelta(minutes=booking.duration_minutes)
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:l360-booking-{booking.id}@learning360",
            f"DTSTAMP:{_dt(booking.created_at)}",
            f"DTSTART:{_dt(booking.start_utc)}",
            f"DTEND:{_dt(end)}",
            f"SUMMARY:{_escape(client_label)} — {_escape(room_name)}",
            f"LOCATION:{_escape(room_name)}",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
