"""Forgot-password / reset-password flow: token issuance, one-time use,
expiry, and that the endpoint never reveals whether an email is registered."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from l360 import notify
from l360.db import session_scope
from l360.models import PasswordResetToken, User


@pytest.fixture(autouse=True)
def _capture_emails(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


def _issued_token(email: str) -> str:
    with session_scope() as db:
        row = db.scalar(
            select(PasswordResetToken)
            .join(User, User.id == PasswordResetToken.user_id)
            .where(User.email == email, PasswordResetToken.used_at.is_(None))
            .order_by(PasswordResetToken.id.desc())
        )
        assert row is not None
        return row.token


def test_forgot_password_sends_email_for_known_user(admin_client, _capture_emails):
    r = admin_client.post("/api/forgot-password", json={"email": "admin@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert len(_capture_emails) == 1
    to, subject, body = _capture_emails[0]
    assert to == "admin@example.com"
    assert "reset" in subject.lower()
    assert "/?reset=" in body


def test_forgot_password_same_response_for_unknown_email(client, _capture_emails):
    # Never reveals whether the address is registered — same {"ok": True},
    # no email sent.
    r = client.post("/api/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert _capture_emails == []


def test_reset_password_with_valid_token(client, admin_client, _capture_emails):
    admin_client.post("/api/forgot-password", json={"email": "admin@example.com"})
    token = _issued_token("admin@example.com")

    r = client.post("/api/reset-password", json={"token": token, "password": "brand-new-pass123"})
    assert r.status_code == 200

    # Old password no longer works; new one does.
    assert client.post("/api/login", json={"email": "admin@example.com", "password": "adminpass123"}).status_code == 401
    assert client.post("/api/login", json={"email": "admin@example.com", "password": "brand-new-pass123"}).status_code == 200


def test_reset_password_token_is_single_use(client, admin_client, _capture_emails):
    admin_client.post("/api/forgot-password", json={"email": "admin@example.com"})
    token = _issued_token("admin@example.com")

    first = client.post("/api/reset-password", json={"token": token, "password": "first-new-pass123"})
    assert first.status_code == 200

    second = client.post("/api/reset-password", json={"token": token, "password": "second-new-pass123"})
    assert second.status_code == 400


def test_reset_password_rejects_expired_token(client, admin_client, _capture_emails):
    admin_client.post("/api/forgot-password", json={"email": "admin@example.com"})
    token = _issued_token("admin@example.com")

    with session_scope() as db:
        row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token == token))
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)

    r = client.post("/api/reset-password", json={"token": token, "password": "whatever-new-123"})
    assert r.status_code == 400


def test_reset_password_rejects_unknown_token(client):
    r = client.post("/api/reset-password", json={"token": "not-a-real-token", "password": "whatever-new-123"})
    assert r.status_code == 400


def test_new_forgot_password_request_invalidates_earlier_token(admin_client, client, _capture_emails):
    admin_client.post("/api/forgot-password", json={"email": "admin@example.com"})
    old_token = _issued_token("admin@example.com")

    admin_client.post("/api/forgot-password", json={"email": "admin@example.com"})
    new_token = _issued_token("admin@example.com")
    assert new_token != old_token

    # The superseded token no longer works, even though it hasn't expired.
    r = client.post("/api/reset-password", json={"token": old_token, "password": "whatever-new-123"})
    assert r.status_code == 400

    r2 = client.post("/api/reset-password", json={"token": new_token, "password": "whatever-new-123"})
    assert r2.status_code == 200
