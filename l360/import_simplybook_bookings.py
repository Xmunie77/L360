"""One-off: import a SimplyBook.me bookings dump into L360 Bookings.

    python -m l360.import_simplybook_bookings simplybook_dump.json \\
        --default-room "Room 1" --created-by admin@example.com \\
        [--service-type "Fallback name"] [--past-status completed] [--commit]

The dump is a JSON object with a "bookings" array as SimplyBook's
report/REST API returns it — nested provider/service/client objects,
start_datetime/end_datetime in company-local time (shape confirmed against
the live learning360foundationmalta account, 05/09/2026). The older flat
JSON-RPC getBookings shape is accepted too; l360.simplybook_export can
produce either.

Mapping rules:
  * room — SimplyBook has no room concept; instead each office service name
    carries one ("Educator II Office Session Room 4"), so the room number
    is parsed from the service name and matched against the L360 room whose
    name contains the same number. Services without a room number (home /
    school / online sessions, meetings) fall back to --default-room, since
    L360 bookings always occupy a room.
  * service type — the service name minus its "Room N" suffix, matched
    case-insensitively against L360 service type names ("Consultant Office
    Session Room 4" → "Consultant Office Session"), with SERVICE_ALIASES
    translating SimplyBook spellings the price list names differently
    (Session→Visit, half-hour variants) and LATE_CANCELLATIONS turning
    SimplyBook's late-cancellation "services" into status cancelled_late
    with the charge waived. --service-type is the fallback for names with
    no L360 equivalent. A match snapshots the L360 prices onto the booking
    the way the booking API does.
  * client — the SimplyBook client's email against clients.email
    (case-insensitive). Unknown emails are skipped and counted — import
    those clients first (l360.import_clients), then re-run.
  * educator — the SimplyBook provider's email against users.email, else
    the provider's name against users.full_name.
  * status — SimplyBook "canceled" → "cancelled". Everything else becomes
    "confirmed"; past sessions deliberately do NOT become "completed"
    (completed feeds billing, and historical SimplyBook sessions were
    settled outside L360) unless --past-status completed says so.
  * times — Europe/Malta wall clock (same as TIMEZONE) → UTC.

  * 1.5-hour sessions — SimplyBook can't book 90 minutes, so those are
    entered as a full session plus a contiguous "half ..." booking for the
    same child and educator. Such pairs merge into ONE L360 booking (90
    minutes, hourly price plus half). Half-session bookings with no
    adjacent full session are genuine 30-minute sessions and import as
    such at half the hourly price.

Idempotent — a booking whose (client, start time) pair already exists is
skipped, so re-runs only insert what's missing. Dry run by default;
--commit writes.

Log discipline: this runs in GitHub Actions on a PUBLIC repo, so output
carries only ids (SimplyBook booking/client ids, L360 row ids) and room /
service names — never client or educator names, emails, or phone numbers.
Chase individual rows by their SimplyBook id in the SimplyBook admin.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from l360.booking_logic import local_to_utc
from l360.db import session_scope
from l360.models import Booking, Client, Room, ServiceType, User

# Confirmed keys first; older JSON-RPC spellings after. Creation timestamps
# (record_date) are deliberately NOT fallbacks — better to skip a row than
# import it at its booking-creation time.
START_KEYS = ("start_datetime", "start_date_time", "start_date")
END_KEYS = ("end_datetime", "end_date_time", "end_date")
ROOM_RE = re.compile(r"\broom\s*0*(\d+)\s*", re.IGNORECASE)

# SimplyBook service names that don't match the L360 price list verbatim:
# SimplyBook grew "Session"/"half ... session" variants where L360 says
# "Visit" and prices half-hours by duration rather than by name. Keyed by
# the room-stripped, whitespace-normalized, lowercased SimplyBook name
# (the full 66-service list checked against the live account, 05/09/2026).
SERVICE_ALIASES = {
    "consultant home session": "Consultant Home Visit",
    "consultant home half session": "Consultant Home Visit",
    "educator ii home session": "Educator II Home Visit",
    "educator ii home half session": "Educator II Home Visit",
    "educator i home session": "Educator I Home Visit",
    "educator i home half session": "Educator I Home Visit",
    "consultant school session": "Consultant School Visit",
    "consultant school half session": "Consultant School Visit",
    "educator ii school half session": "Educator II School Visit",
    "consultant office half an hour session": "Consultant Office Session",
    "educator ii office half session": "Educator II Office Session",
    "educator i office half session": "Educator I Office Session",
    "initial onboarding meeting": "Onboarding Meeting",
    "review and written update of indepth programme": "Review or Written Update of Indepth Programme",
    "consultant school meeting half hour": "Consultant School Meeting",
    "consultant iep meeting": "IEP",
    "iep consultant half hour": "IEP",
    "educator ii iep meeting": "IEP Educator II",
    "educator ii iep meeting half hour": "IEP Educator II",
}

# SimplyBook models a charged late cancellation as its own bookable
# service; L360 models it as a booking with status "cancelled_late". These
# import with that status and charge_waived=True — whatever was owed was
# settled (or forgiven) inside SimplyBook, and imported history must never
# be re-invoiced by L360 on its own. Value = the underlying L360 service
# type, or None where L360 has no equivalent (partial-fee 24-12h tiers,
# Educator I school visits).
LATE_CANCELLATIONS = {
    "consultant office late cancellation as per policy": "Consultant Office Session",
    "consultant home late cancellation": "Consultant Home Visit",
    "consultant school session late cancellation": "Consultant School Visit",
    "educator ii office late cancellation": "Educator II Office Session",
    "educator ii home late cancellation": "Educator II Home Visit",
    "educator ii school late cancellation": "Educator II School Visit",
    "educator i office late cancellation": "Educator I Office Session",
    "educator i home late cancellation": "Educator I Home Visit",
    "educator i school late cancellation": None,
    "late cancellation 24-12 hours - consultant": None,
    "late cancellation 24-12 hours educator ii": None,
    "late cancellation 24-12 hours educator i": None,
}


def _first(record: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = record.get(k)
        if isinstance(v, (str, int, float)) and str(v).strip():
            return str(v).strip()
    return None


def _parse_local(raw: str) -> datetime:
    # "2026-09-04 10:00:00" (SimplyBook) or ISO with a T.
    return datetime.fromisoformat(raw.replace(" ", "T"))


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().lower()


def _service_name(rec: dict) -> str:
    service = rec.get("service") if isinstance(rec.get("service"), dict) else {}
    return _first(service, ("name",)) or _first(rec, ("event", "event_name", "service_name")) or ""


def _client_email(rec: dict) -> str | None:
    client_obj = rec.get("client") if isinstance(rec.get("client"), dict) else {}
    return _first(client_obj, ("email",)) or _first(rec, ("client_email",))


def _provider_key(rec: dict, providers: dict) -> str:
    provider = rec.get("provider") if isinstance(rec.get("provider"), dict) else None
    if provider is None:
        unit_id = _first(rec, ("provider_id", "unit_id", "unit_group_id"))
        provider = providers.get(unit_id or "", {})
    return str(provider.get("id") or _first(rec, ("provider_id", "unit_id"))
               or provider.get("name") or "")


def _is_cancelled(rec: dict) -> bool:
    return str(rec.get("status", "")).lower() in ("canceled", "cancelled") \
        or any(str(rec.get(k)) in ("1", "True", "true")
               for k in ("is_canceled", "is_cancelled"))


def cmd_import() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dump", help="JSON dump with a 'bookings' array (see module docstring)")
    parser.add_argument("--default-room", required=True,
                        help="L360 room for services whose name has no room number")
    parser.add_argument("--created-by", required=True,
                        help="email of the L360 admin recorded as creator")
    parser.add_argument("--service-type", default=None,
                        help="fallback L360 service type name for unmatched services")
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

    # Provider id → row, for flat records that only carry a provider/unit id.
    providers = dump.get("providers") or {}
    if isinstance(providers, list):
        providers = {str(p.get("id")): p for p in providers if isinstance(p, dict)}

    to_create = 0
    skipped_existing = 0
    skipped: list[str] = []
    unmatched_services: set[str] = set()
    now_utc = datetime.now(timezone.utc)

    with session_scope() as db:
        default_room = db.scalar(select(Room).where(Room.name == args.default_room))
        if default_room is None:
            sys.exit(f"No room named {args.default_room!r}. Existing rooms: "
                     f"{', '.join(db.scalars(select(Room.name)).all()) or '(none)'}")
        # "Room 4" in a SimplyBook service name → the L360 room carrying a 4.
        rooms_by_number: dict[str, Room] = {}
        for room in db.scalars(select(Room).where(Room.active)).all():
            m = re.search(r"(\d+)", room.name)
            if m:
                rooms_by_number.setdefault(m.group(1).lstrip("0") or "0", room)

        creator = db.scalar(select(User).where(User.email == args.created_by.lower()))
        if creator is None:
            sys.exit("No user with the --created-by email to record as creator.")

        fallback_st = None
        if args.service_type:
            fallback_st = db.scalar(select(ServiceType).where(ServiceType.name == args.service_type))
            if fallback_st is None:
                sys.exit(f"No service type named {args.service_type!r}.")
        service_types = {_norm(st.name): st
                         for st in db.scalars(select(ServiceType)).all()}

        clients_by_email = {c.email.lower(): c for c in db.scalars(select(Client)).all()}
        users = db.scalars(select(User).where(User.active)).all()
        users_by_email = {u.email.lower(): u for u in users}
        users_by_name = {_norm(u.full_name): u for u in users}

        # SimplyBook can't book 90 minutes, so a 1.5-hour session is entered
        # as a full session plus a contiguous "half ..." booking for the same
        # child and educator (live-data check, 05/09/2026: 4 of 5 sampled
        # half-sessions were such extensions; the rest are genuine standalone
        # 30-minute sessions and import as such). Absorb each such half into
        # its neighbour: one booking, +30min, +half the hourly price.
        basics: list[dict | None] = []
        for rec in records:
            b = None
            if isinstance(rec, dict):
                try:
                    raw_start = _first(rec, START_KEYS)
                    raw_end = _first(rec, END_KEYS)
                    email = _client_email(rec)
                    b = {
                        "start": _parse_local(raw_start) if raw_start else None,
                        "end": _parse_local(raw_end) if raw_end else None,
                        "email": email.lower() if email else None,
                        "provider": _provider_key(rec, providers),
                        "half": re.search(r"\bhalf\b", _norm(ROOM_RE.sub(" ", _service_name(rec)))) is not None,
                        "cancelled": _is_cancelled(rec),
                    }
                except ValueError:
                    b = None
            basics.append(b)

        absorbed: set[int] = set()
        extra_halves = [0] * len(records)
        extra_minutes = [0] * len(records)
        start_override: list[datetime | None] = [None] * len(records)
        for hi, h in enumerate(basics):
            if (not h or not h["half"] or h["cancelled"]
                    or not h["email"] or not h["start"]):
                continue
            for bi, b in enumerate(basics):
                if (bi == hi or not b or b["half"] or b["cancelled"] or hi in absorbed
                        or b["email"] != h["email"] or b["provider"] != h["provider"]
                        or not b["start"] or not b["end"]):
                    continue
                follows = b["end"] == h["start"]
                precedes = h["end"] is not None and h["end"] == b["start"]
                if follows or precedes:
                    mins = 30
                    if h["end"] is not None:
                        mins = max(1, int((h["end"] - h["start"]).total_seconds() // 60))
                    extra_minutes[bi] += mins
                    extra_halves[bi] += 1
                    if precedes:
                        start_override[bi] = h["start"]
                    absorbed.add(hi)
                    break

        merged = 0
        for i, rec in enumerate(records, start=1):
            if not isinstance(rec, dict):
                skipped.append(f"record #{i}: not an object")
                continue
            if i - 1 in absorbed:
                merged += 1
                continue
            label = f"simplybook booking {rec.get('id', f'#{i}')}"
            provider = rec.get("provider") if isinstance(rec.get("provider"), dict) else {}
            service = rec.get("service") if isinstance(rec.get("service"), dict) else {}
            client_obj = rec.get("client") if isinstance(rec.get("client"), dict) else {}
            if not provider:
                unit_id = _first(rec, ("provider_id", "unit_id", "unit_group_id"))
                provider = providers.get(unit_id or "", {})

            raw_start = _first(rec, START_KEYS)
            if raw_start is None:
                skipped.append(f"{label}: no start time under {START_KEYS}; "
                               f"keys present: {', '.join(sorted(rec))}")
                continue
            try:
                start_local = _parse_local(raw_start)
            except ValueError:
                skipped.append(f"{label}: unparseable start time {raw_start!r}")
                continue
            duration = None
            raw_duration = rec.get("duration")
            if isinstance(raw_duration, (int, float)) and raw_duration > 0:
                duration = int(raw_duration)
            if duration is None:
                raw_end = _first(rec, END_KEYS)
                if raw_end:
                    try:
                        duration = max(1, int((_parse_local(raw_end) - start_local).total_seconds() // 60))
                    except ValueError:
                        pass
            duration = (duration or 60) + extra_minutes[i - 1]
            if start_override[i - 1] is not None:
                start_local = start_override[i - 1]  # an absorbed half precedes

            email = _first(client_obj, ("email",)) or _first(rec, ("client_email",))
            if email is None:
                skipped.append(f"{label}: no client on the record (deleted in SimplyBook?)")
                continue
            client = clients_by_email.get(email.lower())
            if client is None:
                skipped.append(f"{label}: client email not in L360 "
                               f"(simplybook client id {client_obj.get('id', '?')}) — import clients first")
                continue

            p_email = _first(provider, ("email",)) or _first(rec, ("unit_email", "provider_email"))
            p_name = _first(provider, ("name",)) or _first(rec, ("unit", "unit_name", "performer_name"))
            educator = users_by_email.get(p_email.lower()) if p_email else None
            if educator is None and p_name:
                educator = users_by_name.get(_norm(p_name))
            if educator is None:
                skipped.append(f"{label}: no L360 user matches simplybook provider id "
                               f"{provider.get('id', rec.get('provider_id', '?'))}")
                continue

            service_name = _first(service, ("name",)) or _first(rec, ("event", "event_name", "service_name")) or ""
            room_match = ROOM_RE.search(service_name)
            room = rooms_by_number.get(room_match.group(1).lstrip("0") or "0") if room_match else None
            if room is None:
                room = default_room

            base_name = _norm(ROOM_RE.sub(" ", service_name))
            late_cancel = base_name in LATE_CANCELLATIONS
            lookup_name = (LATE_CANCELLATIONS.get(base_name)
                           or SERVICE_ALIASES.get(base_name) or base_name)
            service_type = service_types.get(_norm(lookup_name)) or fallback_st
            if service_type is None and service_name:
                unmatched_services.add(service_name.strip())

            start_utc = local_to_utc(start_local.date(), start_local.time())
            cancelled = str(rec.get("status", "")).lower() in ("canceled", "cancelled") \
                or any(str(rec.get(k)) in ("1", "True", "true")
                       for k in ("is_canceled", "is_cancelled"))
            if cancelled:
                status = "cancelled"
            elif late_cancel:
                status = "cancelled_late"
            elif start_utc < now_utc:
                status = args.past_status
            else:
                status = "confirmed"

            existing = db.scalar(select(Booking).where(
                Booking.client_id == client.id, Booking.start_utc == start_utc))
            if existing is not None:
                skipped_existing += 1
                continue

            # SimplyBook's "half ..." service variants price at exactly half
            # the hourly service (checked against the live service list): a
            # standalone half snapshots half the prices, and each absorbed
            # half adds half the hourly prices on top of the full session.
            client_price = tutor_price = None
            note = ""
            if service_type is not None:
                client_price = service_type.client_price_cents
                tutor_price = service_type.tutor_payment_cents
                if re.search(r"\bhalf\b", base_name):
                    client_price //= 2
                    tutor_price //= 2
                    note = " (half rate)"
                elif extra_halves[i - 1]:
                    client_price += extra_halves[i - 1] * (client_price // 2)
                    tutor_price += extra_halves[i - 1] * (tutor_price // 2)
            if extra_halves[i - 1]:
                note = f" (+{extra_minutes[i - 1]}min half-session merged)"
            st_label = service_type.name if service_type else "no service type"
            print(f"  + {start_local:%Y-%m-%d %H:%M} {duration}min  {label} -> "
                  f"client {client.id}, educator {educator.id}, {room.name}, {st_label}"
                  f"{note} [{status}]")
            to_create += 1
            if args.commit:
                db.add(Booking(
                    room_id=room.id,
                    educator_id=educator.id,
                    client_id=client.id,
                    service_type_id=service_type.id if service_type else None,
                    client_price_cents=client_price,
                    tutor_payment_cents=tutor_price,
                    start_utc=start_utc,
                    duration_minutes=duration,
                    status=status,
                    charge_waived=status == "cancelled_late",
                    notes=f"Imported from SimplyBook (id {rec.get('id', '?')}, code {rec.get('code', '?')})",
                    created_by=creator.id,
                    cancelled_at=now_utc if status in ("cancelled", "cancelled_late") else None,
                ))

    verb = "Created" if args.commit else "Would create"
    print(f"{verb} {to_create} booking(s); {merged} half-session(s) merged into "
          f"their adjacent booking; {skipped_existing} already existed; "
          f"{len(skipped)} skipped.")
    for line in skipped:
        print(f"  {line}")
    if unmatched_services:
        print("SimplyBook services with no L360 service type (imported without prices):")
        for name in sorted(unmatched_services):
            print(f"  {name}")
    if not args.commit:
        print("Dry run — re-run with --commit to write.")


if __name__ == "__main__":
    cmd_import()
