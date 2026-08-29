"""Reusable one-off: assign an educator level to an existing user by email.
Having a level is what makes someone bookable as an educator (see
/api/educators) — independent of their admin/educator role, so an admin
who also delivers sessions (a founder, say) can be both.

    L360_USER_EMAIL=... L360_LEVEL_NAME=... python -m l360.set_educator_level
"""
from __future__ import annotations

import os

from sqlalchemy import select

from l360.db import session_scope
from l360.models import EducatorLevel, User


def cmd_set_educator_level() -> None:
    email = os.environ["L360_USER_EMAIL"].strip().lower()
    level_name = os.environ["L360_LEVEL_NAME"].strip()

    with session_scope() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No user found with email {email}.")
            return

        level = db.scalar(select(EducatorLevel).where(EducatorLevel.name == level_name))
        if level is None:
            existing = [row.name for row in db.scalars(select(EducatorLevel))]
            print(f"No educator level named {level_name!r}. Existing levels: {existing}")
            return

        user.level_id = level.id
        print(f"{user.full_name} <{email}> is now level {level_name} — bookable as an educator.")


if __name__ == "__main__":
    cmd_set_educator_level()
