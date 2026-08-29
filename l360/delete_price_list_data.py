"""One-off: delete the old level+duration price list data (the Junior/
Senior/Consultant/Assistant hourly rates seeded via seed_price_list.py).

Booking/billing now price from the L360 price list (service_types) instead
of educator level + duration — see billing_logic.py / statements_logic.py.
This just clears the now-unused PriceListEntry rows; the table, model and
admin API are left in place (dormant, no longer used by any real flow).

Idempotent — a no-op if there's nothing left to delete.

    python -m l360.delete_price_list_data
"""
from __future__ import annotations

from sqlalchemy import delete

from l360.db import session_scope
from l360.models import PriceListEntry


def cmd_delete_price_list_data() -> None:
    with session_scope() as db:
        result = db.execute(delete(PriceListEntry))
        deleted = result.rowcount

    print(f"Deleted {deleted} price list entries.")


if __name__ == "__main__":
    cmd_delete_price_list_data()
