"""One-off: bulk-import real clients from CSV. The CSV never touches git —
it's read from the CLIENTS_CSV_DATA repository secret at run time by the
gated "Import Clients" GitHub Action (workflow_dispatch), so it's encrypted
at rest and masked in logs, never a committed file. Delete that secret once
the import's done; it isn't needed again.

Expected header row (child_dob as YYYY-MM-DD; leave any optional field
blank if unknown):

    guardian_first_name,guardian_surname,email,phone,child_name,child_dob,observations,notes

Idempotent — rows whose email already exists in the DB are skipped, so a
re-run (e.g. to pick up rows fixed after an earlier partial import) only
inserts what's still missing. Rows missing a required field are skipped
and reported, not fatal to the rest of the batch.

    CLIENTS_CSV="$(cat clients.csv)" python -m l360.import_clients
"""
from __future__ import annotations

import csv
import io
import os
from datetime import date

from sqlalchemy import select

from l360.db import session_scope
from l360.models import Client

REQUIRED_FIELDS = ("guardian_first_name", "guardian_surname", "email")
OPTIONAL_FIELDS = ("phone", "child_name", "observations", "notes")


def _parse_dob(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    return date.fromisoformat(raw)


def cmd_import_clients() -> None:
    csv_text = os.environ["CLIENTS_CSV"]
    reader = csv.DictReader(io.StringIO(csv_text))

    created = 0
    skipped_existing = 0
    skipped_invalid: list[str] = []

    with session_scope() as db:
        for i, row in enumerate(reader, start=2):  # row 1 is the header
            row = {k: (v or "").strip() for k, v in row.items()}
            missing = [f for f in REQUIRED_FIELDS if not row.get(f)]
            if missing:
                skipped_invalid.append(f"row {i}: missing {', '.join(missing)}")
                continue

            email = row["email"].lower()
            if db.scalar(select(Client).where(Client.email == email)) is not None:
                skipped_existing += 1
                continue

            try:
                dob = _parse_dob(row.get("child_dob", ""))
            except ValueError:
                skipped_invalid.append(f"row {i}: bad child_dob {row.get('child_dob')!r} (expected YYYY-MM-DD)")
                continue

            db.add(Client(
                guardian_first_name=row["guardian_first_name"],
                guardian_surname=row["guardian_surname"],
                email=email,
                phone=row.get("phone") or None,
                child_name=row.get("child_name") or None,
                child_dob=dob,
                observations=row.get("observations") or None,
                notes=row.get("notes") or None,
            ))
            created += 1

    print(f"Created {created} client(s); {skipped_existing} already existed; {len(skipped_invalid)} skipped as invalid.")
    for line in skipped_invalid:
        print(f"  {line}")


if __name__ == "__main__":
    cmd_import_clients()
