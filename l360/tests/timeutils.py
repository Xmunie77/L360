"""Shared midnight-safe time anchors for booking tests.

RULE: never build a booking start from bare `now() + timedelta(...)`.
Facility hours end at local midnight, so a fixed offset from "now" crosses
midnight whenever the suite runs late evening — this exact flake was fixed
six separate times (30-31/08/2026) before being consolidated here.
"""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from l360.booking_logic import local_to_utc, utc_to_local


def safe_morning_start(days_ahead: int = 2) -> datetime:
    """Local 09:00 Malta, days_ahead from today — immune to midnight
    crossings even after a few hours' offset is added on top, and always
    >24h out (worst case ~33h), so cancellation-cutoff assumptions hold."""
    return local_to_utc((datetime.now(UTC) + timedelta(days=days_ahead)).date(), time(9, 0))


def safe_future_start(hours_ahead: int) -> datetime:
    """now()+hours, but nudged off local hour 23 (the only hour where a
    60-minute session crosses midnight). Only moves earlier within the same
    date, so 24h-window semantics relative to now are preserved."""
    dt_utc = datetime.now(UTC) + timedelta(hours=hours_ahead)
    local_date, local_time = utc_to_local(dt_utc)
    if local_time.hour == 23:
        local_time = local_time.replace(hour=21, minute=0, second=0, microsecond=0)
    return local_to_utc(local_date, local_time)


def inside_cutoff_start() -> datetime:
    """A start within the 24h cancellation cutoff, anchored so a 60-minute
    session never crosses local midnight."""
    local_date, local_time = utc_to_local(datetime.now(UTC))
    if local_time.hour < 21:
        return local_to_utc(local_date, local_time.replace(hour=local_time.hour + 2, minute=0, second=0, microsecond=0))
    return local_to_utc(local_date + timedelta(days=1), time(9, 0))
