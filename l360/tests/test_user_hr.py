"""Admin-only HR details on staff accounts (/api/admin/users/{id}/hr)."""


def _an_educator_id(admin_client):
    r = admin_client.post("/api/admin/users", json={
        "email": "hr.educator@example.com",
        "full_name": "HR Educator",
        "role": "educator",
        "password": "educatorpass123",
        "send_onboarding": False,
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_hr_roundtrip_admin_only(admin_client, educator_client):
    uid = _an_educator_id(admin_client)

    blank = admin_client.get(f"/api/admin/users/{uid}/hr")
    assert blank.status_code == 200
    assert blank.json()["iban"] is None

    saved = admin_client.put(f"/api/admin/users/{uid}/hr", json={
        "iban": "MT50MMEB44587000000058190489001",
        "id_card_number": "0123456M",
        "address": "1, Test Street, Swatar",
        "nationality": "Maltese",
        "emergency_name": "  Pat Test  ",
    })
    assert saved.status_code == 200
    assert saved.json()["iban"] == "MT50MMEB44587000000058190489001"
    assert saved.json()["emergency_name"] == "Pat Test"  # stripped
    assert saved.json()["mobile"] is None

    # Educators can't reach the HR endpoints at all.
    assert educator_client.get(f"/api/admin/users/{uid}/hr").status_code == 403
    assert educator_client.put(f"/api/admin/users/{uid}/hr", json={"iban": "X"}).status_code == 403


def test_hr_fields_never_in_general_user_payloads(admin_client):
    uid = _an_educator_id(admin_client)
    admin_client.put(f"/api/admin/users/{uid}/hr", json={"iban": "MT99TEST", "id_card_number": "999M"})

    listing = admin_client.get("/api/admin/users")
    row = next(u for u in listing.json() if u["id"] == uid)
    for banned in ("iban", "id_card_number", "address", "social_security_number", "date_of_birth"):
        assert banned not in row, f"{banned} leaked into the users listing"
