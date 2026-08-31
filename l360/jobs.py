"""Scheduled jobs: T-24h session reminders and each educator's daily digest.

Deliberately NOT started automatically inside the FastAPI app: the
Dockerfile runs `UVICORN_WORKERS=2`, and starting an in-process scheduler
per worker would mean every job fires twice a run (NotificationLog's
unique dedupe_key makes that harmless, not efficient). Run this as its own
process instead: `python -m l360.jobs`. See l360/DEPLOY.md for wiring that
into a second Fly process.

The two send_* functions are the actual logic and are directly unit
testable without any scheduler involved.
"""
from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime, time, timedelta, UTC
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from l360 import notify
from l360.booking_logic import local_to_utc, utc_to_local
from l360.config import TIMEZONE
from l360.models import Booking, Client, User


def send_24h_reminders(db: Session, *, now: datetime | None = None) -> int:
    """Confirmed bookings starting in the next 24h that haven't been
    reminded yet. Returns the count of reminders actually sent."""
    now = now or datetime.now(UTC)
    window_end = now + timedelta(hours=24)
    rows = db.scalars(
        select(Booking).where(
            Booking.status == "confirmed",
            Booking.start_utc > now,
            Booking.start_utc <= window_end,
        )
    ).all()

    sent = 0
    for booking in rows:
        educator = db.get(User, booking.educator_id)
        client = db.get(Client, booking.client_id)
        local_date, local_time = utc_to_local(booking.start_utc)
        when = f"{local_date.strftime('%A %d %B %Y')} at {local_time.strftime('%H:%M')}"
        subject = f"Reminder — session {when}"
        body = f"Reminder: session with {client.guardian_name if client else '?'} {when}."

        for email, user_id in filter(None, [
            (educator.email, educator.id) if educator and educator.email else None,
            (client.email, None) if client and client.email else None,
        ]):
            dedupe_key = f"reminder_24h:{booking.id}:{email}"
            if notify.send_once(db, to=email, subject=subject, body=body, booking_id=booking.id, user_id=user_id, kind="reminder_24h", dedupe_key=dedupe_key):
                sent += 1
    return sent


def send_daily_digest(db: Session, *, today: date_cls | None = None) -> int:
    """Each active educator with at least one confirmed session today gets
    one summary email. Returns the count of digests actually sent."""
    today = today or datetime.now(ZoneInfo(TIMEZONE)).date()
    day_start = local_to_utc(today, time(0, 0))
    day_end = local_to_utc(today, time(23, 59, 59))

    # Anyone with a level assigned delivers sessions and gets a digest —
    # not just role="educator" (an admin who's also an educator counts too).
    educators = db.scalars(select(User).where(User.level_id.is_not(None), User.active == True)).all()  # noqa: E712
    sent = 0
    for educator in educators:
        bookings = db.scalars(
            select(Booking)
            .where(
                Booking.educator_id == educator.id,
                Booking.status == "confirmed",
                Booking.start_utc >= day_start,
                Booking.start_utc <= day_end,
            )
            .order_by(Booking.start_utc)
        ).all()
        if not bookings:
            continue

        clients = {c.id: c for c in db.scalars(select(Client).where(Client.id.in_({b.client_id for b in bookings})))}
        lines = []
        for b in bookings:
            client = clients.get(b.client_id)
            _, local_time = utc_to_local(b.start_utc)
            lines.append(f"{local_time.strftime('%H:%M')} — {client.guardian_name if client else '?'}")
        body = "Today's sessions:\n" + "\n".join(lines)
        dedupe_key = f"digest:{today.isoformat()}:{educator.id}"
        if notify.send_once(
            db, to=educator.email, subject=f"Your sessions today ({today.strftime('%d %B')})", body=body,
            booking_id=None, user_id=educator.id, kind="digest", dedupe_key=dedupe_key,
        ):
            sent += 1
    return sent


def start_scheduler():
    """Blocking entrypoint for `python -m l360.jobs` — a separate process
    from the web app (see module docstring)."""
    from apscheduler.schedulers.blocking import BlockingScheduler

    from l360.db import session_scope

    def _run_reminders():
        with session_scope() as db:
            send_24h_reminders(db)

    def _run_digest():
        with session_scope() as db:
            send_daily_digest(db)

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(_run_reminders, "interval", minutes=15, id="reminders_24h")
    scheduler.add_job(_run_digest, "cron", hour=6, minute=0, id="daily_digest")  # ~07/08 Malta local
    scheduler.start()


if __name__ == "__main__":
    start_scheduler()
