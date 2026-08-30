"""Admin email (SMTP) settings — DB-stored config editable in-app, password
write-only, env fallback, and the test-send endpoint."""
from __future__ import annotations

from l360 import notify


def _save(admin_client, **overrides):
    body = {
        "host": "smtp.gmail.com",
        "port": 587,
        "user": "info@example.org",
        "email_from": "info@example.org",
        "password": "app-password-123",
    }
    body.update(overrides)
    r = admin_client.put("/api/admin/email-settings", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_settings_roundtrip_and_password_write_only(admin_client):
    r = admin_client.get("/api/admin/email-settings")
    assert r.status_code == 200
    assert r.json()["password_set"] is False

    saved = _save(admin_client)
    assert saved["host"] == "smtp.gmail.com"
    assert saved["password_set"] is True
    assert "password" not in saved  # never echoed back

    # Re-saving with a blank password keeps the stored one.
    saved = _save(admin_client, password=None, port=465)
    assert saved["password_set"] is True
    assert saved["port"] == 465

    cfg = notify.smtp_config()
    assert cfg["host"] == "smtp.gmail.com"
    assert cfg["port"] == 465
    assert cfg["password"] == "app-password-123"


def test_send_email_uses_db_config(admin_client, monkeypatch):
    _save(admin_client)

    calls = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            calls["host"], calls["port"] = host, port

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            calls["tls"] = True

        def login(self, user, password):
            calls["login"] = (user, password)

        def send_message(self, msg):
            calls["to"] = msg["To"]
            calls["from"] = msg["From"]

    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    notify.send_email("parent@example.com", "hi", "body")
    assert calls["host"] == "smtp.gmail.com"
    assert calls["login"] == ("info@example.org", "app-password-123")
    assert calls["to"] == "parent@example.com"
    assert calls["from"] == "info@example.org"


def test_test_endpoint_reports_failure_and_success(admin_client, monkeypatch):
    # No host configured → honest failure, no exception.
    r = admin_client.post("/api/admin/email-settings/test")
    assert r.status_code == 200
    assert r.json()["ok"] is False

    _save(admin_client)
    monkeypatch.setattr(notify, "send_email", lambda to, subject, body, attachment=None: None)
    r = admin_client.post("/api/admin/email-settings/test")
    assert r.json()["ok"] is True

    def _boom(to, subject, body, attachment=None):
        raise OSError("connection refused")

    monkeypatch.setattr(notify, "send_email", _boom)
    r = admin_client.post("/api/admin/email-settings/test")
    assert r.json()["ok"] is False
    assert "connection refused" in r.json()["detail"]


def test_settings_are_admin_only(educator_client):
    assert educator_client.get("/api/admin/email-settings").status_code == 403
    assert educator_client.put("/api/admin/email-settings", json={"host": "x", "port": 587, "user": "", "email_from": ""}).status_code == 403
    assert educator_client.post("/api/admin/email-settings/test").status_code == 403


def test_settings_normalise_pasted_url_and_spaced_password(admin_client, monkeypatch):
    """The two real-world entry mistakes from the first live setup: a
    browser-mangled host URL and a Google app password pasted with spaces."""
    r = admin_client.put("/api/admin/email-settings", json={
        "host": "http://smtp.gmail.com/",
        "port": 587,
        "user": "info@example.org",
        "email_from": "info@example.org",
        "password": "abcd efgh ijkl mnop",
    })
    assert r.status_code == 200
    assert r.json()["host"] == "smtp.gmail.com"
    cfg = notify.smtp_config()
    assert cfg["host"] == "smtp.gmail.com"
    assert cfg["password"] == "abcdefghijklmnop"
