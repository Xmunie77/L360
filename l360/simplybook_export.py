"""One-off: export bookings (plus service/provider lookups) from a
SimplyBook.me account into a JSON dump, ready for
``python -m l360.import_simplybook_bookings``.

Run this from a machine that can reach *.simplybook.me — it only talks to
SimplyBook, never to the L360 database, so it needs no DB credentials:

    SIMPLYBOOK_COMPANY=yourcompanylogin \\
    SIMPLYBOOK_API_KEY=xxxxxxxx \\
    python -m l360.simplybook_export --out simplybook_dump.json

The API key comes from the SimplyBook admin interface: Custom Features →
API → Settings ("API custom feature" must be enabled on the account).

Protocol notes (SimplyBook "User API", JSON-RPC 2.0 over HTTPS):
  * auth: call getToken(company_login, api_key) on
    https://user-api.simplybook.me/login — returns a token valid ~1 hour;
  * admin service: https://user-api.simplybook.me/admin with headers
    X-Company-Login / X-Token;
  * getBookings / getBookingDetails / getEventList / getUnitList are the
    documented admin methods used here.
The getBookings *filter* shape isn't pinned down by us — by default we call
it with an empty filter (which per SimplyBook's docs returns bookings) and
print the count; if that count doesn't match what the SimplyBook calendar
shows, pass ``--filter '{"date_from": "2020-01-01"}'`` etc. after checking
https://help.simplybook.me/index.php/Company_administration_service_methods
for the exact keys.

The dump is raw API output on purpose: whatever field names SimplyBook
returns are preserved verbatim, so the importer (and a human) can inspect
them before anything touches the L360 database. Bookings can contain
personal data — treat the dump file like the clients CSV: keep it out of
git and delete it after the import.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

LOGIN_URL = "https://user-api.simplybook.me/login"
ADMIN_URL = "https://user-api.simplybook.me/admin"


class SimplyBookError(RuntimeError):
    pass


def _rpc(client: httpx.Client, url: str, method: str, params: list[Any],
         headers: dict[str, str] | None = None) -> Any:
    resp = client.post(url, json={
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }, headers=headers or {})
    resp.raise_for_status()
    body = resp.json()
    if body.get("error"):
        raise SimplyBookError(f"{method} failed: {body['error']}")
    return body.get("result")


def cmd_export() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="simplybook_dump.json",
                        help="output JSON path (default simplybook_dump.json)")
    parser.add_argument("--filter", default="{}",
                        help="JSON object passed to getBookings as its filter argument")
    parser.add_argument("--details", action="store_true",
                        help="also call getBookingDetails per booking (slower; one call each)")
    args = parser.parse_args()

    company = os.environ.get("SIMPLYBOOK_COMPANY", "").strip()
    api_key = os.environ.get("SIMPLYBOOK_API_KEY", "").strip()
    if not company or not api_key:
        sys.exit("Set SIMPLYBOOK_COMPANY and SIMPLYBOOK_API_KEY (see module docstring).")

    booking_filter = json.loads(args.filter)

    with httpx.Client(timeout=60) as client:
        token = _rpc(client, LOGIN_URL, "getToken", [company, api_key])
        headers = {"X-Company-Login": company, "X-Token": token}

        bookings = _rpc(client, ADMIN_URL, "getBookings", [booking_filter], headers)
        # Lookup tables so ids in the bookings are resolvable offline.
        services = _rpc(client, ADMIN_URL, "getEventList", [], headers)
        providers = _rpc(client, ADMIN_URL, "getUnitList", [], headers)

        if isinstance(bookings, dict):
            # Some SimplyBook list methods return {id: row, ...} maps.
            bookings = list(bookings.values())

        details: dict[str, Any] = {}
        if args.details:
            for i, b in enumerate(bookings, start=1):
                booking_id = b.get("id") if isinstance(b, dict) else None
                if booking_id is None:
                    continue
                details[str(booking_id)] = _rpc(
                    client, ADMIN_URL, "getBookingDetails", [booking_id], headers)
                if i % 25 == 0:
                    print(f"  …details {i}/{len(bookings)}")

    dump = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "company": company,
        "filter": booking_filter,
        "bookings": bookings,
        "services": services,
        "providers": providers,
        "booking_details": details,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=2, ensure_ascii=False, default=str)

    print(f"Exported {len(bookings)} booking(s) to {args.out}.")
    print("Compare that count against the SimplyBook calendar; if bookings are "
          "missing, re-run with an explicit --filter (see module docstring).")
    if bookings and isinstance(bookings[0], dict):
        print(f"Booking fields seen: {', '.join(sorted(bookings[0]))}")


if __name__ == "__main__":
    cmd_export()
