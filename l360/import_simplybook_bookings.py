"""One-off: import a SimplyBook.me dump (from l360.simplybook_export) into
L360 Bookings.

    python -m l360.import_simplybook_bookings simplybook_dump.json \\
        --room "Room 1" --created-by simon@rubiconmalta.com \\
        [--service-type "Consultant Office Session"] [--commit]

Dry-run by default: without --commit nothing is written — the run prints
what would be created and every row it can't map, so the first pass against
real data doubles as a field-name check on the dump.

Mapping rules:
  * client  → matched by email against clients.email (case-insensitive).
    SimplyBook bookings whose client email isn't in L360 are skipped and
    listed — import those clients first (l360.import_clients).
  * educator → matched by the SimplyBook provider ("unit") email, else by
    name against users.full_name (case-insensitive). Unmatched → skipped.
  * room / service type / created_by are global for the run (SimplyBook has
    no L360 room concept), given by name/email on the CLI. --service-type
    is optional; when set, the service type's prices are snapshotted onto
    each booking the way the booking API does.
  * times: SimplyBook reports wall-clock times in the company timezone,
    which for us is Europe/Malta — same as TIMEZONE — converted to UTC via
    booking_logic.local_to_utc.
  * status: cancelled flags → "cancelled"; anything else → "confirmed".
    Deliberately NOT "completed" for past sessions: completed feeds
    billing, and historical SimplyBook sessions were settled outside L360.
    Pass --past-status completed only if those sessions should be invoiced
    by L360.

Idempotent: a booking whose (client, start time) pair already exists is
skipped, so re-runs only insert what's missing.

The dump's field names are SimplyBook's own; this importer reads the
commonly documented ones and, when a required field is absent, says which
keys the record actually has instead of guessing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from l360.booking_logic import local_to_utc
from l360.db import session_scope
from l360.models import Booking, Client, Room, ServiceType, User

# Key candidates per field — SimplyBook has shipped several list shapes over
# the years; first present key wins. A miss is reported, never guessed.
START_KEYS = ("start_date_time", "start_date", "record_date")
END_KEYS = ("end_date_time", "end_date")
CLIENT_EMAIL_KEYS = ("client_email", "email")
PROVIDER_NAME_KEYS = ("unit", "unit_name", "provider", "performer_name")
PROVIDER_EMAIL_KEYS = ("unit_email", "provider_email")
CANCEL_KEYS = ("is_canceled", "is_cancelled", "canceled", "cancelled")


def _first(record: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = record.get(k)
        if v not in (None, ""):
            return str(v)
    return None


def _parse_local(raw: str) -> datetime:
    # "2026-09-04 10:00:00" (SimplyBook) or ISO with a T.
    return datetime.fromisoformat(raw.replace(" ", "T"))


def cmd_import() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dump", help="JSON file written by l360.simplybook_export")
    parser.add_argument("--room", required=True, help="L360 room name for all imported bookings")
    parser.add_argument("--created-by", required=True, help="email of the L360 admin recorded as creator")
    parser.add_argument("--service-type", default=None, help="optional L360 service type name")
    parser.add_argument("--past-status", choices=("confirmed", "completed"), default="confirmed",
                        help="status for sessions already in the past (default confirmed; "
                             "completed makes them billable by L360)")
    parser.add_argument("--commit", action="store_true", help="actually write (default: dry run)")
    args = parser.parse_args()

    with open(args.dump, encoding="utf-8") as f:
        dump = json.load(f)
    records = dump.get("bookings") or []
    if isinstance(records, dict):
        records = list(records.values())
    details = dump.get("booking_details") or {}

    # Provider id → row from the dump, to resolve unit ids to names/emails.
    providers = dump.get("providers") or {}
    if isinstance(providers, list):
        providers = {str(p.get("id")): p for p in providers if isinstance(p, dict)}

    to_create = 0
    skipped_existing = 0
    skipped: list[str] = []
    now_utc = datetime.now(timezone.utc)

    with session_scope() as db:
        room = db.scalar(select(Room).where(Room.name == args.room))
        if room is None:
            sys.exit(f"No room named {args.room!r}. Existing rooms: "
                     f"{', '.join(db.scalars(select(Room.name)).all()) or '(none)'}")
        creator = db.scalar(select(User).where(User.email == args.created_by.lower()))
        if creator is None:
            sys.exit(f"No user with email {args.created_by!r} to record as creator.")
        service_type = None
        if args.service_type:
            service_type = db.scalar(select(ServiceType).where(ServiceType.name == args.service_type))
            if service_type is None:
                sys.exit(f"No service type named {args.service_type!r}.")

        clients_by_email = {c.email.lower(): c for c in db.scalars(select(Client)).all()}
        users = db.scalars(select(User).where(User.active)).all()
        users_by_email = {u.email.lower(): u for u in users}
        users_by_name = {u.full_name.strip().lower(): u for u in users}

        for i, rec in enumerate(records, start=1):
            if not isinstance(rec, dict):
                skipped.append(f"record {i}: not an object")
                continue
            # Merge in per-booking details when the export fetched them —
            # they usually carry the client email when the list row doesn't.
            det = details.get(str(rec.get("id")))
            merged = {**(det if isinstance(det, dict) else {}), **rec}
            label = f"record {i} (simplybook id {merged.get('id', '?')})"

            raw_start = _first(merged, START_KEYS)
            if raw_start is None:
                skipped.append(f"{label}: no start time under {START_KEYS}; "
                               f"keys present: {', '.join(sorted(merged))}")
                continue
            try:
                start_local = _parse_local(raw_start)
            except ValueError:
                skipped.append(f"{label}: unparseable start time {raw_start!r}")
                continue

            raw_end = _first(merged, END_KEYS)
            duration = 60
            if raw_end:
                try:
                    duration = max(1, int((_parse_local(raw_end) - start_local).total_seconds() // 60))
                except ValueError:
                    pass  # keep the 60-minute default, noted in the summary line

            email = _first(merged, CLIENT_EMAIL_KEYS)
            client_obj = merged.get("client")
            if email is None and isinstance(client_obj, dict):
                email = _first(client_obj, CLIENT_EMAIL_KEYS)
            if email is None:
                skipped.append(f"{label}: no client email under {CLIENT_EMAIL_KEYS}; "
                               f"keys present: {', '.join(sorted(merged))}")
                continue
            client = clients_by_email.get(email.lower())
            if client is None:
                skipped.append(f"{label}: client {email} not in L360 — import clients first")
                continue

            unit_id = merged.get("unit_id") or merged.get("unit_group_id")
            provider = providers.get(str(unit_id), {}) if unit_id is not None else {}
            p_email = _first(merged, PROVIDER_EMAIL_KEYS) or _first(provider, PROVIDER_EMAIL_KEYS + ("email",))
            p_name = _first(merged, PROVIDER_NAME_KEYS) or _first(provider, ("name",))
            educator = None
            if p_email:
                educator = users_by_email.get(p_email.lower())
            if educator is None and p_name:
                educator = users_by_name.get(p_name.strip().lower())
            if educator is None:
                skipped.append(f"{label}: no L360 user matches provider "
                               f"{p_name or p_email or unit_id!r}")
                continue

            start_utc = local_to_utc(start_local.date(), start_local.time())

            cancelled = any(str(merged.get(k)) in ("1", "True", "true") for k in CANCEL_KEYS) \
                or str(merged.get("status", "")).lower() in ("canceled", "cancelled")
            if cancelled:
                status = "cancelled"
            elif start_utc < now_utc:
                status = args.past_status
            else:
                status = "confirmed"

            existing = db.scalar(select(Booking).where(
                Booking.client_id == client.id, Booking.start_utc == start_utc))
            if existing is not None:
                skipped_existing += 1
                continue

            print(f"  + {start_local:%Y-%m-%d %H:%M} {duration}min  {client.email}  "
                  f"with {educator.full_name}  [{status}]")
            to_create += 1
            if args.commit:
                db.add(Booking(
                    room_id=room.id,
                    educator_id=educator.id,
                    client_id=client.id,
                    service_type_id=service_type.id if service_type else None,
                    client_price_cents=service_type.client_price_cents if service_type else None,
                    tutor_payment_cents=service_type.tutor_payment_cents if service_type else None,
                    start_utc=start_utc,
                    duration_minutes=duration,
                    status=status,
                    notes=f"Imported from SimplyBook (id {merged.get('id', '?')})",
                    created_by=creator.id,
                    cancelled_at=now_utc if status == "cancelled" else None,
                ))

    verb = "Created" if args.commit else "Would create"
    print(f"{verb} {to_create} booking(s); {skipped_existing} already existed; "
          f"{len(skipped)} skipped.")
    for line in skipped:
        print(f"  {line}")
    if not args.commit:
        print("Dry run — re-run with --commit to write.")


if __name__ == "__main__":
    cmd_import()
