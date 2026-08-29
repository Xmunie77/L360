"""Onboarding questionnaire — auto-invite on client creation, the public
token-authed form flow, the admin status/resend endpoints, and the Google
Form responses importer."""
from __future__ import annotations

import os

from sqlalchemy import select

from l360.db import session_scope
from l360.models import NotificationLog, OnboardingForm


def _create_client(admin_client, **overrides):
    body = {
        "guardian_first_name": "Jane",
        "guardian_surname": "Doe",
        "email": "jane@example.com",
        "child_name": "JD",
    }
    body.update(overrides)
    r = admin_client.post("/api/admin/clients", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _valid_submission(**overrides):
    body = {
        "guardian_first_name": "Jane",
        "guardian_surname": "Doe",
        "email": "jane@example.com",
        "phone": "79000000",
        "guardian_id_number": "123456M",
        "child_name": "Junior Doe",
        "child_dob": "2016-05-04",
        "school": "San Anton",
        "address": "1, Triq it-Test, Swatar",
        "has_allergies": False,
        "fee_undertaking": True,
        "termination_60d_ack": True,
        "info_storage_consent": True,
        "marketing_opt_in": False,
        "epinephrine_ack": True,
        "accident_ack": True,
        "cancellation_policy_ack": True,
        "illness_policy_ack": True,
        "signature_guardian1": "Jane Doe",
        "signed_date": "2026-08-29",
    }
    body.update(overrides)
    return body


def _token_for(client_id: int) -> str:
    with session_scope() as db:
        form = db.scalar(select(OnboardingForm).where(OnboardingForm.client_id == client_id))
        assert form is not None
        return form.token


def test_create_client_auto_creates_and_sends_form(admin_client):
    created = _create_client(admin_client)
    assert created["onboarding_status"] == "pending"

    r = admin_client.get(f"/api/admin/clients/{created['id']}/onboarding")
    assert r.status_code == 200
    form = r.json()
    assert form["status"] == "pending"
    assert form["sent_at"] is not None
    assert "?onboarding=" in form["link"]

    with session_scope() as db:
        sends = db.scalars(select(NotificationLog).where(NotificationLog.kind == "onboarding_invite")).all()
        assert len(sends) == 1


def test_public_get_prefills_and_submit_updates_client(admin_client, client):
    created = _create_client(admin_client)
    token = _token_for(created["id"])

    r = client.get(f"/api/onboarding/{token}")
    assert r.status_code == 200
    prefill = r.json()
    assert prefill["status"] == "pending"
    assert prefill["guardian_first_name"] == "Jane"
    assert prefill["child_name"] == "JD"

    r = client.post(f"/api/onboarding/{token}", json=_valid_submission())
    assert r.status_code == 200, r.text

    detail = admin_client.get(f"/api/admin/clients/{created['id']}").json()
    assert detail["guardian_id_number"] == "123456M"
    assert detail["child_name"] == "Junior Doe"
    assert detail["address"] == "1, Triq it-Test, Swatar"
    assert detail["has_allergies"] is False
    assert detail["onboarding_status"] == "submitted"

    form = admin_client.get(f"/api/admin/clients/{created['id']}/onboarding").json()
    assert form["status"] == "submitted"
    assert form["marketing_opt_in"] is False
    assert form["signature_guardian1"] == "Jane Doe"

    # Second submission is refused.
    r = client.post(f"/api/onboarding/{token}", json=_valid_submission())
    assert r.status_code == 409


def test_submit_requires_every_mandatory_consent(admin_client, client):
    created = _create_client(admin_client)
    token = _token_for(created["id"])
    r = client.post(f"/api/onboarding/{token}", json=_valid_submission(accident_ack=False))
    assert r.status_code == 422
    # An honest marketing "no" is fine (checked in the happy-path test);
    # allergy details become required when has_allergies is true.
    r = client.post(f"/api/onboarding/{token}", json=_valid_submission(has_allergies=True))
    assert r.status_code == 422


def test_unknown_token_404(client):
    assert client.get("/api/onboarding/not-a-real-token").status_code == 404
    assert client.post("/api/onboarding/not-a-real-token", json=_valid_submission()).status_code == 404


def test_admin_resend_and_submitted_guard(admin_client, client):
    created = _create_client(admin_client)
    r = admin_client.post(f"/api/admin/clients/{created['id']}/onboarding/send")
    assert r.status_code == 200
    with session_scope() as db:
        sends = db.scalars(select(NotificationLog).where(NotificationLog.kind == "onboarding_invite")).all()
        assert len(sends) == 2  # auto-send + explicit resend

    token = _token_for(created["id"])
    assert client.post(f"/api/onboarding/{token}", json=_valid_submission()).status_code == 200
    assert admin_client.post(f"/api/admin/clients/{created['id']}/onboarding/send").status_code == 409


def test_update_with_partial_body_does_not_wipe_new_fields(admin_client, client):
    created = _create_client(admin_client)
    token = _token_for(created["id"])
    assert client.post(f"/api/onboarding/{token}", json=_valid_submission()).status_code == 200

    # An old-style update payload (pre-onboarding fields only) must leave the
    # onboarding-sourced fields untouched.
    r = admin_client.put(f"/api/admin/clients/{created['id']}", json={
        "guardian_first_name": "Jane",
        "guardian_surname": "Doe",
        "email": "jane@example.com",
        "notes": "spoke on the phone",
        "active": True,
    })
    assert r.status_code == 200
    detail = r.json()
    assert detail["guardian_id_number"] == "123456M"
    assert detail["address"] == "1, Triq it-Test, Swatar"
    assert detail["notes"] == "spoke on the phone"


_SHEET_CSV = '''Timestamp,Name and Surname of Parent/Guardian 1 or Persons of legal age,I.D. Number of Parent/Guardian 1 or Persons of legal age,Email address of Parent/Guardian 1 or persons of legal age,Contact number of Parent/Guardian 1 or persons of legal age,Name and Surname of Parent/Guardian 2 ,I.D. Number of Parent/Guardian 2,Email address of Parent/Guardian 2,Contact number of Parent/Guardian 2,Name and Surname of Learner,Date of Birth of Learner,School Learner attends,Address,Does the learner have any allergies? ,"If the learner has any allergies, please specify what they are:","I undertake to pay all fees due for the services rendered to the minor under my care or for the learner of legal age by Learning 360° Foundation \n",I understand that Learning 360° Foundation has the right to terminate services if payment for services is not received for more than 60 days,I agree to have my information stored by Learning 360° Foundation and shared with the relevant tutor if or when necessary. ,Would you like to be kept informed about new services offered by Learning 360 Foundation?,Signature of Parent/Guardian 1/ Learner of legal age,Signature of Parent/Guardian 2 ,Date,Email Address,"I understand that if the learner has an allergy, the Educators at Learning 36O Foundation are not trained to use Epipens or allergy medication nor will be responsible to do so. ",I acknowledge that educators at Learning 360 Foundation are not to be held liable for any accidents that may occur while a learner is in their care. ,I agree to the cancellation policy: ,I agree to the illness policy:
9/11/2023 11:34:27,Philippa Test,462384M,ptest@example.com,99898938,Keith Test ,48285M,ktest@example.com,79859555,Ana Test ,8/25/2016,San Miguel,"8, Kwadra, Triq il-Harruba, Iklin",Yes,Milk protein ,Yes,Yes,Yes,Yes,Philippa Test,Keith Test ,9/10/2023,,Yes,Yes,Yes,Yes
9/12/2023 09:00:00,Old Entry,111111M,ptest@example.com,99111111,,,,,Ana Test,8/25/2016,San Miguel,"8, Kwadra, Iklin",No,,Yes,Yes,Yes,No,Philippa Test,,9/12/2023,,Yes,Yes,Yes,Yes
9/11/2023 12:00:00,No Email,123M,,,,,,,Kid X,1/2/2015,,Somewhere,No,,Yes,Yes,Yes,Yes,No Email,,9/11/2023,,,,,
'''


def test_import_form_responses(admin_client):
    from l360 import import_form_responses

    # An existing client with the same email keeps admin-entered basics but
    # gains the onboarding record + missing fields.
    existing = _create_client(admin_client, email="ptest@example.com", guardian_first_name="Philippa", guardian_surname="Test")

    os.environ["FORM_RESPONSES_CSV"] = _SHEET_CSV
    os.environ.pop("FORM_RESPONSES_CSV_FILE", None)
    try:
        import_form_responses.cmd_import()
    finally:
        del os.environ["FORM_RESPONSES_CSV"]

    detail = admin_client.get(f"/api/admin/clients/{existing['id']}").json()
    # Latest row for the email wins (the 9/12 re-submission).
    assert detail["guardian_id_number"] == "111111M"
    assert detail["school"] == "San Miguel"
    assert detail["child_dob"] == "2016-08-25"
    assert detail["onboarding_status"] == "submitted"

    form = admin_client.get(f"/api/admin/clients/{existing['id']}/onboarding").json()
    assert form["source"] == "google_form"
    assert form["marketing_opt_in"] is False
    assert form["cancellation_policy_ack"] is True

    # The no-email row was skipped, so only the one imported client exists
    # beyond the pre-existing one.
    clients = admin_client.get("/api/admin/clients").json()
    assert len(clients) == 1

    # Re-running is a no-op (already submitted).
    os.environ["FORM_RESPONSES_CSV"] = _SHEET_CSV
    try:
        import_form_responses.cmd_import()
    finally:
        del os.environ["FORM_RESPONSES_CSV"]
    assert len(admin_client.get("/api/admin/clients").json()) == 1
