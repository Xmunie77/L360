"""One-off: import the legacy Google "Client Onboarding Form" responses.

Reads the Google Sheet's CSV export ("Student Contact Information
(Responses)") and loads it straight into the DB: client details onto
`clients` (created if missing, enriched fill-if-empty when the email already
exists) and the consent/signature answers as a **submitted** OnboardingForm
(source="google_form"), so the legal record of what each guardian agreed to
lives in the OS alongside the client.

The CSV itself NEVER touches git — this is a public repo. Pass the data at
run time, e.g. on the Fly machine:

    fly ssh console -a l360-os
    cat > /tmp/responses.csv   # paste, ^D
    FORM_RESPONSES_CSV_FILE=/tmp/responses.csv python -m l360.import_form_responses
    rm /tmp/responses.csv

or locally: FORM_RESPONSES_CSV="$(cat responses.csv)" python -m l360.import_form_responses

Dry-run by default when DRY_RUN=1 is set. Idempotent:
- one row per email (the latest submission wins when a guardian re-submitted);
- an existing client is enriched, not overwritten — only fields currently
  empty in the DB are filled (admin-curated data always wins);
- a client whose onboarding form is already submitted is left untouched.
"""
from __future__ import annotations

import csv
import io
import os
import re
import secrets
from datetime import UTC, date, datetime

from sqlalchemy import select

from l360.db import session_scope
from l360.models import Client, OnboardingForm
from l360.onboarding import CLIENT_FIELDS

# Normalised-header (lowercased, whitespace-collapsed) → field. Matching is
# "starts with" for the verbose questions (the sheet headers carry trailing
# spaces/newlines and the odd typo — e.g. "Learning 36O"), exact for the
# short ambiguous ones (Address vs "Email address of …").
_PREFIX_MAP = {
    "name and surname of parent/guardian 1": "g1_name",
    "i.d. number of parent/guardian 1": "guardian_id_number",
    "email address of parent/guardian 1": "email",
    "contact number of parent/guardian 1": "phone",
    "name and surname of parent/guardian 2": "guardian2_name",
    "i.d. number of parent/guardian 2": "guardian2_id_number",
    "email address of parent/guardian 2": "guardian2_email",
    "contact number of parent/guardian 2": "guardian2_phone",
    "name and surname of learner": "child_name",
    "date of birth of learner": "child_dob",
    "school learner attends": "school",
    "does the learner have any allergies": "has_allergies",
    "if the learner has any allergies": "allergy_details",
    "i undertake to pay all fees": "fee_undertaking",
    "i understand that learning 360° foundation has the right to terminate": "termination_60d_ack",
    "i agree to have my information stored": "info_storage_consent",
    "would you like to be kept informed": "marketing_opt_in",
    "signature of parent/guardian 1": "signature_guardian1",
    "signature of parent/guardian 2": "signature_guardian2",
    "i understand that if the learner has an allergy": "epinephrine_ack",
    "i acknowledge that educators at learning 360": "accident_ack",
    "i agree to the cancellation policy": "cancellation_policy_ack",
    "i agree to the illness policy": "illness_policy_ack",
}
_EXACT_MAP = {
    "timestamp": "timestamp",
    "address": "address",
    "date": "signed_date",
    "email address": "account_email",
}

_CONSENTS = (
    "fee_undertaking", "termination_60d_ack", "info_storage_consent", "marketing_opt_in",
    "epinephrine_ack", "accident_ack", "cancellation_policy_ack", "illness_policy_ack",
)


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "")).strip().lower()


def _field_for(header: str) -> str | None:
    n = _norm_header(header)
    if n in _EXACT_MAP:
        return _EXACT_MAP[n]
    for prefix, field in _PREFIX_MAP.items():
        if n.startswith(prefix):
            return field
    return None


def _parse_bool(raw: str | None) -> bool | None:
    v = (raw or "").strip().lower()
    if not v:
        return None
    if v in ("yes", "i agree", "true", "agreed"):
        return True
    if v == "no":
        return False
    return None


def _parse_date(raw: str | None) -> date | None:
    """Google Forms exports dates US-style (M/D/YYYY); fall back to D/M/YYYY
    and ISO for hand-edited cells."""
    v = (raw or "").strip()
    if not v:
        return None
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def _parse_timestamp(raw: str | None) -> datetime | None:
    v = (raw or "").strip()
    if not v:
        return None
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(v, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _split_name(full: str) -> tuple[str, str]:
    # Same convention as migration 0006's backfill: split on the last space.
    name = re.sub(r"\s+", " ", full).strip()
    if " " in name:
        first, surname = name.rsplit(" ", 1)
    else:
        first, surname = "", (name or "—")
    return first, surname


def _read_rows(csv_text: str) -> list[dict[str, str]]:
    reader = csv.reader(io.StringIO(csv_text))
    try:
        header = next(reader)
    except StopIteration:
        return []
    fields = [_field_for(h) for h in header]
    rows: list[dict[str, str]] = []
    for raw in reader:
        if not any(cell.strip() for cell in raw):
            continue
        row: dict[str, str] = {}
        for field, value in zip(fields, raw):
            if field and value is not None and value.strip():
                row[field] = value.strip()
        rows.append(row)
    return rows


def cmd_import() -> None:
    if os.environ.get("FORM_RESPONSES_CSV_FILE"):
        with open(os.environ["FORM_RESPONSES_CSV_FILE"], encoding="utf-8-sig") as fh:
            csv_text = fh.read()
    else:
        csv_text = os.environ["FORM_RESPONSES_CSV"]
    dry_run = os.environ.get("DRY_RUN", "").strip() in ("1", "true", "yes")

    rows = _read_rows(csv_text)

    # Latest submission per email wins.
    by_email: dict[str, dict[str, str]] = {}
    problems: list[str] = []
    for i, row in enumerate(rows, start=2):
        email = (row.get("email") or row.get("account_email") or "").lower()
        if "@" not in email:
            problems.append(f"row {i}: no usable email — skipped ({row.get('g1_name', '?')})")
            continue
        row["_email"] = email
        prev = by_email.get(email)
        if prev is None or (
            (_parse_timestamp(row.get("timestamp")) or datetime.min.replace(tzinfo=UTC))
            >= (_parse_timestamp(prev.get("timestamp")) or datetime.min.replace(tzinfo=UTC))
        ):
            by_email[email] = row

    created = enriched = consents_added = skipped_submitted = 0
    with session_scope() as db:
        for email, row in by_email.items():
            first, surname = _split_name(row.get("g1_name", ""))
            dob = _parse_date(row.get("child_dob"))
            if row.get("child_dob") and dob is None:
                problems.append(f"{email}: unparseable learner DOB {row.get('child_dob')!r} — left blank")

            values = {
                "guardian_first_name": first,
                "guardian_surname": surname,
                "email": email,
                "phone": row.get("phone"),
                "guardian_id_number": row.get("guardian_id_number"),
                "guardian2_name": row.get("guardian2_name"),
                "guardian2_id_number": row.get("guardian2_id_number"),
                "guardian2_email": (row.get("guardian2_email") or "").lower() or None,
                "guardian2_phone": row.get("guardian2_phone"),
                "child_name": row.get("child_name"),
                "child_dob": dob,
                "school": row.get("school"),
                "address": row.get("address"),
                "has_allergies": _parse_bool(row.get("has_allergies")),
                "allergy_details": row.get("allergy_details"),
            }

            client = db.scalar(select(Client).where(Client.email == email))
            if client is None:
                client = Client(**values)
                db.add(client)
                db.flush()
                created += 1
            else:
                # Enrich, never overwrite — admin-curated data wins.
                touched = False
                for field in CLIENT_FIELDS:
                    if field in ("guardian_first_name", "guardian_surname", "email"):
                        continue
                    if getattr(client, field) in (None, "") and values[field] not in (None, ""):
                        setattr(client, field, values[field])
                        touched = True
                enriched += touched

            form = db.scalar(select(OnboardingForm).where(OnboardingForm.client_id == client.id))
            if form is not None and form.status == "submitted":
                skipped_submitted += 1
                continue
            if form is None:
                form = OnboardingForm(client_id=client.id, token=secrets.token_urlsafe(32))
                db.add(form)
            for field in _CONSENTS:
                setattr(form, field, _parse_bool(row.get(field)))
            form.signature_guardian1 = row.get("signature_guardian1")
            form.signature_guardian2 = row.get("signature_guardian2")
            form.signed_date = _parse_date(row.get("signed_date"))
            form.status = "submitted"
            form.source = "google_form"
            form.submitted_at = _parse_timestamp(row.get("timestamp")) or datetime.now(UTC)
            consents_added += 1

        if dry_run:
            db.rollback()

    print(
        f"{'DRY RUN — rolled back. ' if dry_run else ''}"
        f"{len(rows)} response rows → {len(by_email)} unique emails. "
        f"Created {created} client(s), enriched {enriched} existing, "
        f"recorded {consents_added} submitted onboarding form(s), "
        f"{skipped_submitted} already submitted (untouched)."
    )
    for line in problems:
        print(f"  {line}")


if __name__ == "__main__":
    cmd_import()
