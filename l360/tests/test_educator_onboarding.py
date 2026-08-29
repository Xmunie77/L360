"""Educator onboarding — auto-invite on educator creation, the public
token-authed form flow, and the admin status/resend endpoints."""
from __future__ import annotations

from sqlalchemy import select

from l360.db import session_scope
from l360.models import EducatorOnboardingForm, NotificationLog


def _create_educator(admin_client, email="ed@example.com"):
    level = admin_client.post("/api/admin/educator-levels", json={"name": "Level X"}).json()
    r = admin_client.post("/api/admin/users", json={
        "email": email,
        "full_name": "Eddy Educator",
        "role": "educator",
        "level_id": level["id"],
        "password": "educatorpass123",
    })
    assert r.status_code == 200, r.text
    return r.json()


def _valid_submission(**overrides):
    body = {
        "full_legal_name": "Edward Educator",
        "date_of_birth": "1990-01-15",
        "id_passport_number": "1234567M",
        "residential_address": "5, Triq it-Taghlim, Swatar",
        "mobile": "79123456",
        "email": "ed@example.com",
        "right_to_work": "yes",
        "emergency_name": "Emma Educator",
        "emergency_phone": "79654321",
        "sg_convicted": "no",
        "sg_proceedings": "no",
        "sg_dismissed": "no",
        "sg_other_matters": "no",
        "b_follow_procedures": True,
        "b_report_concerns": True,
        "b_approved_channels": True,
        "b_no_sharing": True,
        "b_boundaries": True,
        "referee_authorisation": True,
        "dp_accuracy": True,
        "dp_processing": True,
        "signature_name": "Edward Educator",
        "signed_date": "2026-08-29",
        "qualifications": [{"qualification": "B.Ed", "institution": "UoM", "year": "2012", "level_result": "2:1"}],
        "availability": [{"day": "Monday", "available_from": "15:00", "available_until": "19:00", "on_site": True, "online": False, "notes": ""}],
        "credentials": ["teaching_warrant", "first_aid"],
        "iban": "MT00TEST0000000000000000000",
    }
    body.update(overrides)
    return body


def _token_for(user_id: int) -> str:
    with session_scope() as db:
        form = db.scalar(select(EducatorOnboardingForm).where(EducatorOnboardingForm.user_id == user_id))
        assert form is not None
        return form.token


def test_create_educator_auto_sends_form_but_admin_does_not(admin_client):
    created = _create_educator(admin_client)
    assert created["onboarding_status"] == "pending"

    r = admin_client.post("/api/admin/users", json={
        "email": "second.admin@example.com", "full_name": "Second Admin",
        "role": "admin", "password": "adminpass456",
    })
    assert r.status_code == 200
    assert r.json()["onboarding_status"] is None

    with session_scope() as db:
        sends = db.scalars(select(NotificationLog).where(NotificationLog.kind == "educator_onboarding_invite")).all()
        assert len(sends) == 1

    form = admin_client.get(f"/api/admin/users/{created['id']}/onboarding").json()
    assert form["status"] == "pending"
    assert "?educator-onboarding=" in form["link"]
    assert form["answers"] is None


def test_public_get_and_submit(admin_client, client):
    created = _create_educator(admin_client)
    token = _token_for(created["id"])

    prefill = client.get(f"/api/educator-onboarding/{token}").json()
    assert prefill["status"] == "pending"
    assert prefill["full_name"] == "Eddy Educator"

    r = client.post(f"/api/educator-onboarding/{token}", json=_valid_submission())
    assert r.status_code == 200, r.text

    form = admin_client.get(f"/api/admin/users/{created['id']}/onboarding").json()
    assert form["status"] == "submitted"
    assert form["signature_name"] == "Edward Educator"
    assert form["answers"]["full_legal_name"] == "Edward Educator"
    assert form["answers"]["qualifications"][0]["qualification"] == "B.Ed"
    assert form["answers"]["availability"][0]["day"] == "Monday"

    users = admin_client.get("/api/admin/users").json()
    ed = next(u for u in users if u["id"] == created["id"])
    assert ed["onboarding_status"] == "submitted"

    # Resubmit refused; resend refused once submitted.
    assert client.post(f"/api/educator-onboarding/{token}", json=_valid_submission()).status_code == 409
    assert admin_client.post(f"/api/admin/users/{created['id']}/onboarding/send").status_code == 409


def test_submit_requires_declarations(admin_client, client):
    created = _create_educator(admin_client)
    token = _token_for(created["id"])
    assert client.post(f"/api/educator-onboarding/{token}", json=_valid_submission(b_no_sharing=False)).status_code == 422
    assert client.post(f"/api/educator-onboarding/{token}", json=_valid_submission(dp_processing=False)).status_code == 422
    assert client.post(f"/api/educator-onboarding/{token}", json=_valid_submission(referee_authorisation=False)).status_code == 422
    # sg answers must be explicit
    bad = _valid_submission()
    del bad["sg_convicted"]
    assert client.post(f"/api/educator-onboarding/{token}", json=bad).status_code == 422


def test_unknown_token_and_resend(admin_client, client):
    assert client.get("/api/educator-onboarding/nope").status_code == 404
    created = _create_educator(admin_client)
    r = admin_client.post(f"/api/admin/users/{created['id']}/onboarding/send")
    assert r.status_code == 200
    with session_scope() as db:
        sends = db.scalars(select(NotificationLog).where(NotificationLog.kind == "educator_onboarding_invite")).all()
        assert len(sends) == 2  # auto-send + resend
