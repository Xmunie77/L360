"""Idempotent dev/first-deploy seed data.

    python -m l360.seed

Seeds a realistic starting point: 3 educator levels, 5 rooms, 12 educators,
1 admin, a dated price list, and standard facility hours. Rooms/educators
are plain admin-CRUD data with no hard limits — this is just a sensible
starting roster, not a schema constraint.

Refuses to create demo accounts on Postgres unless L360_ALLOW_DEMO_SEED=1,
since the generated passwords are fixed dev-only values.
"""
from __future__ import annotations

import os
from datetime import date, time

from sqlalchemy import select

from l360 import auth
from l360.config import IS_POSTGRES
from l360.db import init_db, session_scope
from l360.models import EducatorLevel, FacilityHours, PriceListEntry, Room, User

LEVELS = ["Junior", "Senior", "Specialist"]
ROOMS = [f"Room {i}" for i in range(1, 6)]

# client_price_cents by (level name, duration_minutes)
CLIENT_PRICES = {
    ("Junior", 60): 3000, ("Junior", 90): 4200, ("Junior", 120): 5500,
    ("Senior", 60): 3800, ("Senior", 90): 5400, ("Senior", 120): 7000,
    ("Specialist", 60): 4800, ("Specialist", 90): 6800, ("Specialist", 120): 8800,
}
PRICE_VALID_FROM = date(2026, 9, 1)


def _educator_rate_cents(client_price_cents: int) -> int:
    # 60% of client price, rounded to the nearest 10 cents.
    return round(client_price_cents * 0.6 / 10) * 10


def cmd_seed() -> None:
    if IS_POSTGRES and os.environ.get("L360_ALLOW_DEMO_SEED") != "1":
        print("Refusing to seed demo accounts on Postgres (set L360_ALLOW_DEMO_SEED=1 to override).")
        return

    init_db()  # no-op on Postgres; creates SQLite tables locally
    with session_scope() as db:
        levels_by_name: dict[str, EducatorLevel] = {}
        for i, name in enumerate(LEVELS):
            row = db.scalar(select(EducatorLevel).where(EducatorLevel.name == name))
            if row is None:
                row = EducatorLevel(name=name, sort_order=i)
                db.add(row)
                db.flush()
            levels_by_name[name] = row

        for i, name in enumerate(ROOMS):
            if db.scalar(select(Room).where(Room.name == name)) is None:
                db.add(Room(name=name, sort_order=i))

        if db.scalar(select(User).where(User.email == "admin@example.com")) is None:
            db.add(User(
                email="admin@example.com",
                full_name="Admin",
                role="admin",
                password_hash=auth.hash_password("l360-admin-dev"),
            ))

        for i in range(1, 13):
            email = f"educator{i}@example.com"
            if db.scalar(select(User).where(User.email == email)) is not None:
                continue
            level = LEVELS[(i - 1) % len(LEVELS)]
            db.add(User(
                email=email,
                full_name=f"Educator {i}",
                role="educator",
                level_id=levels_by_name[level].id,
                password_hash=auth.hash_password("l360-dev"),
            ))

        for (level_name, duration), client_cents in CLIENT_PRICES.items():
            level = levels_by_name[level_name]
            exists = db.scalar(
                select(PriceListEntry).where(
                    PriceListEntry.level_id == level.id,
                    PriceListEntry.duration_minutes == duration,
                    PriceListEntry.valid_from == PRICE_VALID_FROM,
                )
            )
            if exists is None:
                db.add(PriceListEntry(
                    level_id=level.id,
                    duration_minutes=duration,
                    client_price_cents=client_cents,
                    educator_rate_cents=_educator_rate_cents(client_cents),
                    valid_from=PRICE_VALID_FROM,
                ))

        weekday_hours = {
            **{d: (time(8, 0), time(19, 0)) for d in range(0, 5)},  # Mon-Fri
            5: (time(8, 0), time(13, 0)),  # Sat
        }
        for weekday, (open_t, close_t) in weekday_hours.items():
            if db.scalar(select(FacilityHours).where(FacilityHours.weekday == weekday)) is None:
                db.add(FacilityHours(weekday=weekday, open_time=open_t, close_time=close_t))

    print("Seed complete.")


if __name__ == "__main__":
    cmd_seed()
