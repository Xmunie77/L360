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


def test_internal_checklist_roundtrip(admin_client, educator_client):
    created = _create_educator(admin_client)

    # Saving works before the educator has submitted anything.
    r = admin_client.put(f"/api/admin/users/{created['id']}/onboarding/checklist", json={
        "items": {
            "interview": {"status": "complete", "checked_by": "Test Admin", "date": "2026-08-29"},
            "identity": {"status": "na", "checked_by": "Test Admin", "date": "2026-08-29"},
        },
        "approval": {"approved_by": "Test Admin", "start_date": "2026-09-15"},
    })
    assert r.status_code == 200, r.text
    internal = r.json()["internal"]
    assert internal["items"]["interview"]["status"] == "complete"
    assert internal["approval"]["start_date"] == "2026-09-15"

    # Persisted and returned on GET.
    form = admin_client.get(f"/api/admin/users/{created['id']}/onboarding").json()
    assert form["internal"]["items"]["identity"]["status"] == "na"

    # Unknown item keys rejected; admins only; educator accounts only.
    r = admin_client.put(f"/api/admin/users/{created['id']}/onboarding/checklist", json={
        "items": {"made_up_check": {"status": "complete"}},
    })
    assert r.status_code == 422
    assert educator_client.put(f"/api/admin/users/{created['id']}/onboarding/checklist", json={"items": {}}).status_code == 403
    admins = [u for u in admin_client.get("/api/admin/users").json() if u["role"] == "admin"]
    assert admin_client.put(f"/api/admin/users/{admins[0]['id']}/onboarding/checklist", json={"items": {}}).status_code == 409


def test_contract_generation(admin_client, client):
    created = _create_educator(admin_client)
    # Refused before the form is submitted — nothing to pre-fill from.
    assert admin_client.get(f"/api/admin/users/{created['id']}/onboarding/contract").status_code == 409

    token = _token_for(created["id"])
    assert client.post(f"/api/educator-onboarding/{token}", json=_valid_submission()).status_code == 200

    r = admin_client.get(f"/api/admin/users/{created['id']}/onboarding/contract")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "Services Agreement" in r.headers["content-disposition"]
    assert r.content[:2] == b"PK"  # a real docx (zip container)

    import io
    from docx import Document
    text = "\n".join(p.text for p in Document(io.BytesIO(r.content)).paragraphs)
    assert "Edward Educator" in text            # tutor name merged
    assert "1234567M" in text                   # ID merged
    assert "MT00TEST0000000000000000000" in text  # IBAN merged
    assert "GOVERNING LAW AND JURISDICTION" in text
    # Founders' personal ID numbers must never appear (public repo).
    assert "0307016L" not in text
