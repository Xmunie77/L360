"""Admin CRUD round-trips: rooms, educator levels, clients, users, price
list "as of" resolution, facility hours upsert."""
from __future__ import annotations

from datetime import date


def test_room_crud_roundtrip(admin_client):
    r = admin_client.post("/api/admin/rooms", json={"name": "Room A", "sort_order": 1})
    assert r.status_code == 200
    room = r.json()
    assert room["name"] == "Room A"

    r = admin_client.get("/api/admin/rooms")
    assert any(x["name"] == "Room A" for x in r.json())

    r = admin_client.put(f"/api/admin/rooms/{room['id']}", json={"name": "Room A2", "sort_order": 2})
    assert r.status_code == 200
    assert r.json()["name"] == "Room A2"

    r = admin_client.delete(f"/api/admin/rooms/{room['id']}")
    assert r.status_code == 200
    # deactivated, not hard-deleted: no longer in the public active list
    assert not any(x["name"] == "Room A2" for x in admin_client.get("/api/rooms").json())


def test_educator_level_crud(admin_client):
    r = admin_client.post("/api/admin/educator-levels", json={"name": "Senior", "sort_order": 1})
    assert r.status_code == 200
    level = r.json()
    r = admin_client.put(
        f"/api/admin/educator-levels/{level['id']}",
        json={"name": "Senior II", "sort_order": 1, "active": True},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Senior II"


def test_client_crud(admin_client):
    r = admin_client.post(
        "/api/admin/clients",
        json={"guardian_first_name": "Jane", "guardian_surname": "Doe", "email": "jane@example.com", "child_name": "JD"},
    )
    assert r.status_code == 200
    client_row = r.json()
    assert client_row["guardian_first_name"] == "Jane"
    assert client_row["guardian_surname"] == "Doe"

    r = admin_client.get("/api/clients")
    brief = next(x for x in r.json() if x["id"] == client_row["id"])
    assert brief["child_name"] == "JD"
    assert "email" not in brief  # brief shape hides contact details
    assert "observations" not in brief  # sensitive — admins only

    r = admin_client.get(f"/api/admin/clients/{client_row['id']}")
    assert r.status_code == 200
    assert r.json()["email"] == "jane@example.com"

    assert admin_client.get("/api/admin/clients/999999").status_code == 404


def test_clients_ordered_alphabetically_by_surname(admin_client):
    admin_client.post("/api/admin/clients", json={"guardian_first_name": "Bob", "guardian_surname": "Zeta", "email": "z@example.com"})
    admin_client.post("/api/admin/clients", json={"guardian_first_name": "Amy", "guardian_surname": "Abela", "email": "a@example.com"})
    r = admin_client.get("/api/admin/clients")
    surnames = [c["guardian_surname"] for c in r.json()]
    assert surnames == sorted(surnames)


def test_user_create_and_role_gate(admin_client):
    level = admin_client.post("/api/admin/educator-levels", json={"name": "Junior", "sort_order": 0}).json()
    r = admin_client.post(
        "/api/admin/users",
        json={
            "email": "new.educator@example.com",
            "full_name": "New Educator",
            "role": "educator",
            "level_id": level["id"],
            "password": "supersecret123",
        },
    )
    assert r.status_code == 200
    user = r.json()
    assert user["role"] == "educator"

    # duplicate email rejected
    r = admin_client.post(
        "/api/admin/users",
        json={
            "email": "new.educator@example.com",
            "full_name": "Dupe",
            "role": "educator",
            "password": "supersecret123",
        },
    )
    assert r.status_code == 409

    r = admin_client.put(f"/api/admin/users/{user['id']}", json={"active": False})
    assert r.status_code == 200
    assert r.json()["active"] is False


def test_price_list_as_of_picks_latest_valid_from(admin_client):
    level = admin_client.post("/api/admin/educator-levels", json={"name": "Junior", "sort_order": 0}).json()

    admin_client.post("/api/admin/price-list", json={
        "level_id": level["id"], "duration_minutes": 60,
        "client_price_cents": 3000, "educator_rate_cents": 1800,
        "valid_from": "2026-01-01",
    })
    admin_client.post("/api/admin/price-list", json={
        "level_id": level["id"], "duration_minutes": 60,
        "client_price_cents": 3500, "educator_rate_cents": 2100,
        "valid_from": "2026-06-01",
    })

    # Before the price change: old price applies.
    r = admin_client.get("/api/price-list/current", params={"as_of": "2026-03-01"})
    entries = r.json()
    match = next(e for e in entries if e["level_id"] == level["id"] and e["duration_minutes"] == 60)
    assert match["client_price_cents"] == 3000

    # After the price change: new price applies, old one never mutated.
    r = admin_client.get("/api/price-list/current", params={"as_of": "2026-07-01"})
    entries = r.json()
    match = next(e for e in entries if e["level_id"] == level["id"] and e["duration_minutes"] == 60)
    assert match["client_price_cents"] == 3500


def test_facility_hours_upsert(admin_client):
    r = admin_client.put("/api/admin/facility-hours", json={
        "weekday": 0, "open_time": "08:00:00", "close_time": "19:00:00",
    })
    assert r.status_code == 200
    first_id = r.json()["id"]

    # Upsert same weekday again — updates in place, no duplicate row.
    r = admin_client.put("/api/admin/facility-hours", json={
        "weekday": 0, "open_time": "09:00:00", "close_time": "18:00:00",
    })
    assert r.status_code == 200
    assert r.json()["id"] == first_id
    assert r.json()["open_time"] == "09:00:00"

    rows = admin_client.get("/api/admin/facility-hours").json()
    assert len([x for x in rows if x["weekday"] == 0]) == 1


def test_facility_closure_crud(admin_client):
    r = admin_client.post("/api/admin/closures", json={"date": str(date(2026, 12, 25)), "reason": "Christmas"})
    assert r.status_code == 200
    closure = r.json()
    r = admin_client.delete(f"/api/admin/closures/{closure['id']}")
    assert r.status_code == 200
    assert not any(c["id"] == closure["id"] for c in admin_client.get("/api/admin/closures").json())
