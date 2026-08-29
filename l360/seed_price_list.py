"""One-off: seed the price list from the foundation's real per-hour rates,
prorated for 90/120-minute sessions. Creates the Junior/Senior/Consultant
educator levels if they don't already exist. Idempotent — skips any
(level, duration) combination that already has a price effective today,
and the DB's own unique constraint (level, duration, valid_from) is a
second line of defence against duplicates either way.

    python -m l360.seed_price_list

Rates (per hour, client / educator — the difference is the foundation's
contribution, matching the founders' own pricing sheet):
    Junior      (Educator I)   EUR 35 / EUR 30
    Senior      (Educator II)  EUR 40 / EUR 33
    Consultant                 EUR 45 / EUR 35
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from l360.db import session_scope
from l360.models import EducatorLevel, PriceListEntry

# name -> (sort_order, client price/hour cents, educator rate/hour cents)
HOURLY_RATES = {
    "Junior": (0, 3500, 3000),
    "Senior": (1, 4000, 3300),
    "Consultant": (2, 4500, 3500),
}
DURATIONS = (60, 90, 120)


def cmd_seed_price_list() -> None:
    today = date.today()
    created = 0
    with session_scope() as db:
        for name, (sort_order, client_hourly, educator_hourly) in HOURLY_RATES.items():
            level = db.scalar(select(EducatorLevel).where(EducatorLevel.name == name))
            if level is None:
                level = EducatorLevel(name=name, sort_order=sort_order)
                db.add(level)
                db.flush()
                print(f"Created educator level: {name}")

            for duration in DURATIONS:
                factor = duration / 60
                existing = db.scalar(
                    select(PriceListEntry).where(
                        PriceListEntry.level_id == level.id,
                        PriceListEntry.duration_minutes == duration,
                        PriceListEntry.valid_from == today,
                    )
                )
                if existing is not None:
                    continue
                db.add(PriceListEntry(
                    level_id=level.id,
                    duration_minutes=duration,
                    client_price_cents=round(client_hourly * factor),
                    educator_rate_cents=round(educator_hourly * factor),
                    valid_from=today,
                ))
                created += 1

    total = len(HOURLY_RATES) * len(DURATIONS)
    print(f"Created {created} price list entries; {total - created} already existed for today.")


if __name__ == "__main__":
    cmd_seed_price_list()
