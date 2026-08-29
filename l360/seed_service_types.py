"""One-off: seed the named session/additional-service price list from the
foundation's real pricing sheet (Description | Unit Rate | Tutor Payment |
Foundation Contribution — client price = tutor payment + foundation
contribution on every row). These sit alongside, not instead of, the
existing level+duration price list. "Additional services" (flashcards) are
not calendar bookings; everything else is a bookable session type.

Idempotent — skips any name that already exists (matches the DB's own
unique constraint on name).

    python -m l360.seed_service_types

requires_room: whether the session occupies one of the foundation's own
rooms. Home/school visits and meetings happen off-site, so they don't.
Additional services aren't calendar bookings at all, so the field doesn't
apply to them (stored as False) — everything else defaults to True. This
is a judgement call from the item names, not confirmed row-by-row against
the foundation; adjust per-row in the admin UI if any of these are wrong.

Known gaps in the source sheet (left out deliberately rather than guessed):
    - No "Educator I School Visit" row exists on the sheet (Educator II and
      Consultant both have one). Flag to the foundation for the real figure.

Known simplification:
    - "Joint session (consultant and educator)" pays 20/20 split between two
      people on the sheet; bookings only support one assigned educator today,
      so the combined EUR 40 tutor payment is stored as a single total.
"""
from __future__ import annotations

from sqlalchemy import select

from l360.db import session_scope
from l360.models import ServiceType

# name -> (category, sort_order, client_price_cents, tutor_payment_cents, requires_room)
SERVICE_TYPES = {
    "Onboarding Meeting": ("session", 0, 3000, 2500, True),
    "Indepth Programme": ("session", 1, 15000, 12000, True),
    "Snapshot Programme": ("session", 2, 8000, 7000, True),
    "Consultant Office Session": ("session", 3, 3500, 3000, True),
    "Educator II Office Session": ("session", 4, 3000, 2200, True),
    "Educator I Office Session": ("session", 5, 2700, 2000, True),
    "Consultant Home Visit": ("session", 6, 4000, 3500, False),
    "Educator II Home Visit": ("session", 7, 3400, 2700, False),
    "Educator I Home Visit": ("session", 8, 3200, 2500, False),
    "Consultant School Visit": ("session", 9, 4000, 3500, False),
    "Educator II School Visit": ("session", 10, 3400, 2700, False),
    "Consultant School Meeting": ("session", 11, 5500, 5000, False),
    "Review or Written Update of Programme Snapshot": ("session", 12, 5500, 5000, True),
    "Review or Written Update of Indepth Programme": ("session", 13, 5500, 5000, True),
    "Initial Consultation Meeting": ("session", 14, 5500, 5000, True),
    "Review Meeting": ("session", 15, 5500, 5000, True),
    "Joint Session (Consultant and Educator)": ("session", 16, 5000, 4000, True),
    "IEP": ("session", 17, 5500, 5000, True),
    "IEP Educator II": ("session", 18, 3500, 3000, True),
    "Joint Session Educator": ("session", 19, 5000, 3000, True),
    "Session Educator 3 Students": ("session", 20, 7500, 4000, True),
    "Session Educator 2 Students": ("session", 21, 5000, 3500, True),
    "Home Session 2 Students": ("session", 22, 9000, 5000, False),
    "Flashcards A4": ("additional_service", 0, 120, 50, False),
    "Flashcards A5": ("additional_service", 1, 60, 25, False),
}


def cmd_seed_service_types() -> None:
    created = 0
    with session_scope() as db:
        for name, (category, sort_order, client_price, tutor_payment, requires_room) in SERVICE_TYPES.items():
            existing = db.scalar(select(ServiceType).where(ServiceType.name == name))
            if existing is not None:
                continue
            db.add(ServiceType(
                name=name,
                category=category,
                client_price_cents=client_price,
                tutor_payment_cents=tutor_payment,
                requires_room=requires_room,
                sort_order=sort_order,
            ))
            created += 1

    total = len(SERVICE_TYPES)
    print(f"Created {created} service types; {total - created} already existed.")


if __name__ == "__main__":
    cmd_seed_service_types()
