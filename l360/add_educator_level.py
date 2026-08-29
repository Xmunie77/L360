"""One-off: add a new educator level. Idempotent — a no-op if a level with
this name already exists.

    L360_LEVEL_NAME=... L360_LEVEL_SORT_ORDER=... python -m l360.add_educator_level

Adding "Assistant" below the existing Junior/Senior/Consultant tiers, as a
support role for someone not yet working solo — sort_order -1 puts it
first regardless of the other levels' exact values, without needing to
renumber them.

Note: this only creates the level. It has no price list entry until one
is added (Admin -> Price list, or seed_price_list.py-style script) — until
then it exists but isn't priced for booking/billing.
"""
from __future__ import annotations

import os

from sqlalchemy import select

from l360.db import session_scope
from l360.models import EducatorLevel


def cmd_add_educator_level() -> None:
    name = os.environ["L360_LEVEL_NAME"].strip()
    sort_order = int(os.environ.get("L360_LEVEL_SORT_ORDER", "0"))

    with session_scope() as db:
        existing = db.scalar(select(EducatorLevel).where(EducatorLevel.name == name))
        if existing is not None:
            print(f"Educator level {name!r} already exists — nothing to do.")
            return

        db.add(EducatorLevel(name=name, sort_order=sort_order))
        print(f"Created educator level {name!r} (sort_order={sort_order}).")


if __name__ == "__main__":
    cmd_add_educator_level()
