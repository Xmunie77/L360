"""One-off importer: staff bios + headshots from the Drive "HR → Bios" docs.

Each bio is a Google Doc holding one paragraph and an embedded headshot.
This script takes a JSON payload prepared OUTSIDE the repo (client/staff
data never enters git — Simon's standing order) and writes it to the
users table, matching on email.

Payload shape (a list):
    [{"email": "...", "full_name": "...", "bio": "...",
      "photo_b64": "...", "photo_content_type": "image/jpeg"}, ...]

Usage (run where DATABASE_URL points at the target DB):
    python -m l360.import_educator_bios payload.json [--create-missing]

`--create-missing` creates an account for anyone not already in the users
table, with a random password and NO onboarding invite (these are existing
staff, not applicants — they get a password-reset link instead).

Importing a photo records image consent with source "import": the
foundation's GDPR consent form covers photo/image use, and the Bios docs
were assembled from it.
"""
from __future__ import annotations

import base64
import json
import secrets
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from l360 import auth
from l360.db import session_scope
from l360.models import User


def import_bios(payload: list[dict], *, create_missing: bool = False) -> dict:
    created, updated, skipped = [], [], []
    with session_scope() as db:
        for entry in payload:
            email = (entry.get("email") or "").strip().lower()
            if not email:
                skipped.append(f"{entry.get('full_name', '?')}: no email")
                continue
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                if not create_missing:
                    skipped.append(f"{email}: no account (use --create-missing)")
                    continue
                user = User(
                    email=email,
                    full_name=entry.get("full_name") or email,
                    role="educator",
                    # Random throwaway — they set their own via "Forgot password".
                    password_hash=auth.hash_password(secrets.token_urlsafe(24)),
                )
                db.add(user)
                db.flush()
                created.append(email)
            else:
                updated.append(email)

            if entry.get("bio"):
                user.bio = entry["bio"].strip()
            if entry.get("photo_b64"):
                user.photo = base64.b64decode(entry["photo_b64"])
                user.photo_content_type = entry.get("photo_content_type") or "image/jpeg"
                if user.image_consent_at is None:
                    user.image_consent_at = datetime.now(UTC)
                    user.image_consent_source = "import"
    return {"created": created, "updated": updated, "skipped": skipped}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        raise SystemExit(2)
    payload = json.loads(open(args[0]).read())
    result = import_bios(payload, create_missing="--create-missing" in sys.argv)
    for key in ("created", "updated", "skipped"):
        print(f"{key}: {len(result[key])}")
        for line in result[key]:
            print(f"  {line}")


if __name__ == "__main__":
    main()
