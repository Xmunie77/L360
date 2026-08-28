"""One-off bootstrap for the very first admin account.

The dev seed (seed.py) refuses to run against Postgres, since its
passwords are fixed, publicly-visible dev values — never appropriate for a
database holding real client billing data. This script creates exactly one
admin user with a freshly generated random password, printed once to
stdout. Run only via the gated "Create Admin" GitHub Action
(workflow_dispatch), never on boot.

Idempotent by refusal: if the email already exists, does nothing rather
than silently resetting a password.

    L360_ADMIN_EMAIL=you@example.com L360_ADMIN_NAME="Your Name" \
        python -m l360.create_admin
"""
from __future__ import annotations

import os
import secrets

from sqlalchemy import select

from l360 import auth
from l360.db import session_scope
from l360.models import User


def cmd_create_admin() -> None:
    email = os.environ["L360_ADMIN_EMAIL"].strip().lower()
    full_name = os.environ.get("L360_ADMIN_NAME", "Admin").strip()
    password = secrets.token_urlsafe(16)

    with session_scope() as db:
        if db.scalar(select(User).where(User.email == email)) is not None:
            print(f"Refusing: a user with email {email} already exists.")
            return
        db.add(User(
            email=email,
            full_name=full_name,
            role="admin",
            password_hash=auth.hash_password(password),
        ))

    print(f"Admin created: {email}")
    print(f"Temporary password: {password}")
    print("Log in now and change this password immediately — Admin -> Users -> edit yourself.")


if __name__ == "__main__":
    cmd_create_admin()
