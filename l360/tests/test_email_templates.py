"""Editable automated-email templates (Admin → Email)."""
from l360 import email_templates


def test_fill_leaves_unknown_placeholders_visible():
    assert email_templates.fill("Hi {name}, see {typo}", {"name": "Sam"}) == "Hi Sam, see {typo}"


def test_every_default_placeholder_is_declared():
    # A default template must only use placeholders it lists — otherwise the
    # admin UI would document the wrong set.
    for tpl in email_templates.DEFAULTS.values():
        declared = {name for name, _ in tpl.placeholders}
        used = set(email_templates._PLACEHOLDER_RE.findall(tpl.subject + tpl.body))
        assert used <= declared, f"{tpl.kind}: undeclared {used - declared}"


def test_list_save_and_reset_roundtrip(admin_client):
    listing = admin_client.get("/api/admin/email-templates")
    assert listing.status_code == 200
    kinds = {t["kind"] for t in listing.json()}
    assert kinds == set(email_templates.DEFAULTS)
    assert all(not t["is_custom"] for t in listing.json())

    saved = admin_client.put(
        "/api/admin/email-templates/reminder_24h",
        json={"subject": "See you {when}!", "body": "Session with {guardian_name} {when}."},
    )
    assert saved.status_code == 200
    assert saved.json()["is_custom"] is True
    assert saved.json()["subject"] == "See you {when}!"
    # The default is still reported alongside, for the reset affordance.
    assert saved.json()["default_subject"] == "Reminder — session {when}"

    reset = admin_client.delete("/api/admin/email-templates/reminder_24h")
    assert reset.status_code == 200
    assert reset.json()["is_custom"] is False
    assert reset.json()["subject"] == "Reminder — session {when}"


def test_saving_default_wording_is_not_custom(admin_client):
    tpl = email_templates.DEFAULTS["digest"]
    saved = admin_client.put(
        "/api/admin/email-templates/digest", json={"subject": tpl.subject, "body": tpl.body}
    )
    assert saved.status_code == 200
    assert saved.json()["is_custom"] is False


def test_blank_or_unknown_rejected(admin_client):
    assert admin_client.put("/api/admin/email-templates/digest", json={"subject": "", "body": "x"}).status_code == 422
    assert admin_client.put("/api/admin/email-templates/nope", json={"subject": "a", "body": "b"}).status_code == 404


def test_override_changes_outgoing_booking_email(admin_client, booking_env, monkeypatch):
    sent = []
    from l360 import notify
    from l360.tests.timeutils import safe_morning_start

    monkeypatch.setattr(notify, "send_email", lambda to, subject, body, attachment=None: sent.append((to, subject, body)))
    admin_client.put(
        "/api/admin/email-templates/confirmation",
        json={"subject": "Booked: {when}", "body": "Dear {guardian_name}, your session is {when}."},
    )
    resp = admin_client.post("/api/bookings", json={
        "room_id": booking_env["room_id"],
        "educator_id": booking_env["educator_id"],
        "client_id": booking_env["client_id"],
        "service_type_id": booking_env["service_type_id"],
        "start_utc": safe_morning_start().isoformat(),
        "duration_minutes": 60,
    })
    assert resp.status_code == 200, resp.text
    assert sent, "confirmation email should have been sent"
    assert any(s[1].startswith("Booked: ") for s in sent)
    assert any("Dear " in s[2] and "your session is" in s[2] for s in sent)
