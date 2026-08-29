"""Test fixtures — isolated SQLite DB + known secrets, set BEFORE import."""
from __future__ import annotations

import os
import tempfile

import pytest

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"
os.environ["L360_SESSION_SECRET"] = "test-secret"
os.environ["COOKIE_SECURE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from l360 import auth  # noqa: E402
from l360.api import app  # noqa: E402
from l360.db import engine, init_db  # noqa: E402
from l360.models import Base, EducatorLevel, User  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(engine)
    init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)


# NOTE: admin_client / educator_client deliberately do NOT depend on the
# `client` fixture — each gets its OWN TestClient (own cookie jar). Sharing
# one TestClient across two "logged in as X" fixtures means the second
# login silently overwrites the first's session cookie, so a test that
# requests both ends up making every call as whichever fixture happened to
# log in last. Independent instances make both sessions usable at once.
@pytest.fixture
def admin_client():
    from l360.db import session_scope
    with session_scope() as db:
        db.add(User(
            email="admin@example.com",
            full_name="Test Admin",
            role="admin",
            password_hash=auth.hash_password("adminpass123"),
        ))
    admin = TestClient(app)
    r = admin.post("/api/login", json={"email": "admin@example.com", "password": "adminpass123"})
    assert r.status_code == 200
    return admin


@pytest.fixture
def educator_client():
    from sqlalchemy import select
    from l360.db import session_scope
    with session_scope() as db:
        level = db.scalar(select(EducatorLevel).where(EducatorLevel.name == "Junior"))
        if level is None:
            level = EducatorLevel(name="Junior", sort_order=0)
            db.add(level)
            db.flush()
        db.add(User(
            email="educator@example.com",
            full_name="Test Educator",
            role="educator",
            level_id=level.id,
            password_hash=auth.hash_password("educatorpass123"),
        ))
    educator = TestClient(app)
    r = educator.post("/api/login", json={"email": "educator@example.com", "password": "educatorpass123"})
    assert r.status_code == 200
    return educator


@pytest.fixture
def booking_env(admin_client):
    """A room, a client, an educator, and round-the-clock facility hours —
    enough scaffolding for booking-engine tests. Returns a dict of ids plus
    a fresh TestClient logged in as the educator (own cookie jar, so it
    can't collide with admin_client's or educator_client's)."""
    room = admin_client.post("/api/admin/rooms", json={"name": "Test Room"}).json()
    level = admin_client.post("/api/admin/educator-levels", json={"name": "Junior"}).json()
    educator = admin_client.post("/api/admin/users", json={
        "email": "booking.educator@example.com",
        "full_name": "Booking Educator",
        "role": "educator",
        "level_id": level["id"],
        "password": "educatorpass123",
    }).json()
    client_row = admin_client.post("/api/admin/clients", json={
        "guardian_first_name": "Jane", "guardian_surname": "Doe", "email": "jane@example.com", "child_name": "JD",
    }).json()
    service_type = admin_client.post("/api/admin/service-types", json={
        "name": "Test Session", "category": "session",
        "client_price_cents": 3500, "tutor_payment_cents": 3000,
    }).json()
    for weekday in range(7):
        admin_client.put("/api/admin/facility-hours", json={
            "weekday": weekday, "open_time": "00:00:00", "close_time": "23:59:59",
        })

    educator_test_client = TestClient(app)
    r = educator_test_client.post(
        "/api/login", json={"email": "booking.educator@example.com", "password": "educatorpass123"}
    )
    assert r.status_code == 200

    return {
        "room_id": room["id"],
        "educator_id": educator["id"],
        "client_id": client_row["id"],
        "service_type_id": service_type["id"],
        "educator_client": educator_test_client,
    }
