"""One-off: rename an existing educator level in place (e.g. "Specialist"
to "Consultant", matching the L360 pricing sheet's own tier names). Renames
the row itself, so existing price list entries and bookings that reference
it by id are unaffected — this is not a data migration, just a display name
fix. Idempotent — a no-op if the old name no longer exists (already renamed)
or the new name already exists.

    L360_LEVEL_OLD_NAME=... L360_LEVEL_NEW_NAME=... python -m l360.rename_educator_level
"""
from __future__ import annotations

import os

from sqlalchemy import select

from l360.db import session_scope
from l360.models import EducatorLevel


def cmd_rename_educator_level() -> None:
    old_name = os.environ["L360_LEVEL_OLD_NAME"].strip()
    new_name = os.environ["L360_LEVEL_NEW_NAME"].strip()

    with session_scope() as db:
        if db.scalar(select(EducatorLevel).where(EducatorLevel.name == new_name)) is not None:
            print(f"An educator level named {new_name!r} already exists — nothing to do.")
            return

        level = db.scalar(select(EducatorLevel).where(EducatorLevel.name == old_name))
        if level is None:
            print(f"No educator level named {old_name!r} — nothing to do.")
            return

        level.name = new_name
        print(f"Renamed educator level {old_name!r} -> {new_name!r}.")


if __name__ == "__main__":
    cmd_rename_educator_level()
