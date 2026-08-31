"""Password hashing + login/session/role-gate behaviour."""
from __future__ import annotations

from l360 import auth


def test_password_hash_roundtrip():
    hashed = auth.hash_password("correct horse battery staple")
    assert auth.verify_password("correct horse battery staple", hashed)
    assert not auth.verify_password("wrong password", hashed)


def test_password_hash_unique_salts():
    a = auth.hash_password("same-password")
    b = auth.hash_password("same-password")
    assert a != b  # different salts


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_login_wrong_password(admin_client, client):
    r = client.post("/api/login", json={"email": "admin@example.com", "password": "nope"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/api/login", json={"email": "nobody@example.com", "password": "whatever123"})
    assert r.status_code == 401


def test_session_and_me(admin_client):
    assert admin_client.get("/api/session").json() == {"authed": True}
    me = admin_client.get("/api/me").json()
    assert me["email"] == "admin@example.com"
    assert me["role"] == "admin"


def test_session_false_when_logged_out(client):
    assert client.get("/api/session").json() == {"authed": False}
    assert client.get("/api/me").status_code == 401


def test_logout_clears_session(admin_client):
    assert admin_client.post("/api/logout").status_code == 200
    assert admin_client.get("/api/session").json() == {"authed": False}


def test_educator_gets_403_on_admin_routes(educator_client):
    assert educator_client.get("/api/admin/rooms").status_code == 403
    assert educator_client.post("/api/admin/rooms", json={"name": "X"}).status_code == 403
    assert educator_client.get("/api/admin/service-types").status_code == 403


def test_educator_can_read_public_lists(educator_client):
    assert educator_client.get("/api/rooms").status_code == 200
    assert educator_client.get("/api/educators").status_code == 200
    assert educator_client.get("/api/clients").status_code == 200


def test_unauthed_requires_login_everywhere(client):
    assert client.get("/api/rooms").status_code == 401
    assert client.get("/api/admin/rooms").status_code == 401


def test_change_my_password(admin_client, client):
    # Wrong current password refused.
    r = admin_client.post("/api/me/password", json={"current_password": "wrong", "new_password": "newpassword99"})
    assert r.status_code == 403

    r = admin_client.post("/api/me/password", json={"current_password": "adminpass123", "new_password": "newpassword99"})
    assert r.status_code == 200

    # Old password dead, new one works.
    assert client.post("/api/login", json={"email": "admin@example.com", "password": "adminpass123"}).status_code == 401
    assert client.post("/api/login", json={"email": "admin@example.com", "password": "newpassword99"}).status_code == 200

    # Anonymous refused.
    from fastapi.testclient import TestClient
    from l360.api import app
    assert TestClient(app).post("/api/me/password", json={"current_password": "x", "new_password": "newpassword99"}).status_code == 401


def test_login_lockout_after_five_failures(admin_client, client):
    for _ in range(5):
        assert client.post("/api/login", json={"email": "admin@example.com", "password": "nope-wrong"}).status_code == 401
    # Correct password now ALSO refused — the account is locked.
    assert client.post("/api/login", json={"email": "admin@example.com", "password": "adminpass123"}).status_code == 401

    # Expire the lock manually and confirm recovery + counter reset.
    from sqlalchemy import select
    from l360.db import session_scope
    from l360.models import User
    with session_scope() as db:
        u = db.scalar(select(User).where(User.email == "admin@example.com"))
        assert u.locked_until is not None
        u.locked_until = None
    r = client.post("/api/login", json={"email": "admin@example.com", "password": "adminpass123"})
    assert r.status_code == 200
    with session_scope() as db:
        u = db.scalar(select(User).where(User.email == "admin@example.com"))
        assert u.failed_logins == 0 and u.locked_until is None


def test_password_change_invalidates_existing_sessions(admin_client):
    assert admin_client.get("/api/me").status_code == 200
    r = admin_client.post("/api/me/password", json={"current_password": "adminpass123", "new_password": "brandnewpass1"})
    assert r.status_code == 200
    # The same cookie no longer authenticates.
    assert admin_client.get("/api/me").status_code == 401
