"""One-off: insert 10 obviously-fake test clients for trying out bookings,
invoicing, etc. before real client data lands. Idempotent — skips any that
already exist by email. Run only via the gated "Seed Test Clients" GitHub
Action (workflow_dispatch), never on boot.

    python -m l360.seed_test_clients
"""
from __future__ import annotations

from sqlalchemy import select

from l360.db import session_scope
from l360.models import Client

TEST_CLIENTS = [
    {"guardian_name": f"Test Client {i}", "email": f"test-client-{i}@example.com",
     "child_reference": f"Test Child {i}"}
    for i in range(1, 11)
]


def cmd_seed_test_clients() -> None:
    created = 0
    with session_scope() as db:
        for data in TEST_CLIENTS:
            if db.scalar(select(Client).where(Client.email == data["email"])) is not None:
                continue
            db.add(Client(**data, notes="TEST DATA — safe to delete."))
            created += 1
    print(f"Created {created} test client(s); {len(TEST_CLIENTS) - created} already existed.")


if __name__ == "__main__":
    cmd_seed_test_clients()
