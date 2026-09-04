import { useEffect, useState } from "react";
import { Button, Card, Input, StatusBadge } from "../ui/ui";
import {
  ApiError,
  adminGetEducatorOnboarding,
  adminSaveEducatorChecklist,
  adminSendEducatorOnboarding,
  getMe,
  type ChecklistApproval,
  type ChecklistItem,
  type ChecklistStatus,
  type EducatorChecklist,
  type AvailabilityRow,
  type EducatorOnboardingAdmin,
  type ExperienceRow,
  type QualificationRow,
  type RefereeInput,
} from "../api/client";
import {
  CREDENTIAL_OPTIONS,
  DIGITAL_OPTIONS,
  EXPERIENCE_OPTIONS,
  POLICY_OPTIONS,
  SESSION_OPTIONS,
  SG_DOCUMENT_OPTIONS,
} from "./EducatorOnboarding";

// Read-only admin view of an educator's submitted onboarding form, opened
// in its own tab from the Admin -> Users list (?educator-form=<user id>) —
// same pattern as the client detail page. Also hosts the send/re-send
// button while the form is still pending.

const OPTION_LABELS: Record<string, string> = Object.fromEntries(
  [...CREDENTIAL_OPTIONS, ...EXPERIENCE_OPTIONS, ...DIGITAL_OPTIONS, ...SESSION_OPTIONS, ...SG_DOCUMENT_OPTIONS, ...POLICY_OPTIONS],
);

const CHOICE_LABELS: Record<string, string> = {
  employee: "Employee", self_employed: "Self-employed", sessional: "Sessional contractor", tbc: "To be confirmed",
  phone: "Phone", email: "Email", whatsapp: "WhatsApp",
  yes: "Yes", no: "No", pending: "Pending", some: "Some periods", within: "Within a distance", na: "Not applicable",
  maltese_eu: "Maltese / EU / EEA / Swiss", single_permit: "Single Permit", other: "Other",
  payroll: "Payroll", self_invoice: "Self-employed invoice",
};

function fmt(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (v === true) return "Yes";
  if (v === false) return "No";
  const s = String(v);
  return CHOICE_LABELS[s] ?? s;
}

function fmtList(v: unknown): string {
  if (!Array.isArray(v) || v.length === 0) return "—";
  return v.map((item) => OPTION_LABELS[String(item)] ?? String(item)).join(" · ");
}

function Rows({ rows }: { rows: [string, string][] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="l360-table">
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label}>
              <td style={{ width: "40%" }}>{label}</td>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


// Section 15 of the paper form — the internal onboarding checklist. Keys
// mirror educator_onboarding.CHECKLIST_ITEMS server-side.
const CHECKLIST_ITEMS: [string, string][] = [
  ["application_reviewed", "Application reviewed and role confirmed"],
  ["interview", "Interview completed"],
  ["identity", "Identity verified against original"],
  ["right_to_work", "Right to work verified"],
  ["qualifications", "Qualifications / warrant verified"],
  ["police_cert", "Police conduct certificate reviewed"],
  ["minors_clearance", "Applicable minors / safeguarding clearance completed"],
  ["references", "Two references received and satisfactory"],
  ["employment_status", "Employment status confirmed"],
  ["contract", "Contract / service agreement signed"],
  ["rate_approved", "Rate and payment terms approved"],
  ["payroll_setup", "Payroll / supplier setup completed"],
  ["emergency_contact", "Emergency contact recorded"],
  ["sg_induction", "Safeguarding induction completed"],
  ["policies_issued", "Policies issued and acknowledgements received"],
  ["it_access", "IT / system access approved"],
  ["timetable", "Timetable, location and reporting line confirmed"],
  ["data_access", "Data access restricted to role requirements"],
];

const emptyItem = (): ChecklistItem => ({ status: "pending", checked_by: "", date: "" });
const emptyApproval = (): ChecklistApproval => ({
  educator_ref: "", approved_roles: "", approved_locations: "", sg_restrictions: "",
  start_date: "", approved_by: "", signature: "", approval_date: "",
});

function InternalChecklist({
  userId, initial, adminName,
}: {
  userId: number;
  initial: EducatorChecklist | null;
  adminName: string;
}) {
  const [items, setItems] = useState<Record<string, ChecklistItem>>(() => {
    const base: Record<string, ChecklistItem> = {};
    for (const [key] of CHECKLIST_ITEMS) base[key] = initial?.items?.[key] ?? emptyItem();
    return base;
  });
  const [approval, setApproval] = useState<ChecklistApproval>(initial?.approval ?? emptyApproval());
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const doneCount = CHECKLIST_ITEMS.filter(([k]) => items[k].status !== "pending").length;
  const allDone = doneCount === CHECKLIST_ITEMS.length;

  function setStatus(key: string, status: ChecklistStatus) {
    setItems((prev) => ({
      ...prev,
      [key]: {
        status,
        // Auto-stamp who/when the first time a check moves off pending;
        // both stay editable below.
        checked_by: status === "pending" ? prev[key].checked_by : prev[key].checked_by || adminName,
        date: status === "pending" ? prev[key].date : prev[key].date || new Date().toISOString().slice(0, 10),
      },
    }));
  }

  function setItemField(key: string, field: "checked_by" | "date", value: string) {
    setItems((prev) => ({ ...prev, [key]: { ...prev[key], [field]: value } }));
  }

  function setApprovalField(field: keyof ChecklistApproval, value: string) {
    setApproval((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await adminSaveEducatorChecklist(userId, { items, approval });
      setMessage("Checklist saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't save the checklist.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card eyebrow="15 · Internal" title={`Internal onboarding checklist — ${doneCount}/${CHECKLIST_ITEMS.length} addressed`}>
      <p style={{ color: allDone ? "var(--l360-bgrey)" : "var(--l360-danger)", marginBottom: 12 }}>
        Internal use only. Do not schedule unsupervised learner contact until all mandatory
        checks for the role are complete and authorised.
      </p>
      {error && <div className="l360-alert l360-alert-danger" role="alert">⚠ {error}</div>}
      {message && <div className="l360-alert l360-alert-info" role="status">{message}</div>}
      <div style={{ overflowX: "auto", marginBottom: 16 }}>
        <table className="l360-table">
          <thead>
            <tr>
              <th>Check / action</th>
              <th>Status</th>
              <th>Checked by</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            {CHECKLIST_ITEMS.map(([key, label]) => (
              <tr key={key}>
                <td>{label}</td>
                <td>
                  <select
                    className="l360-select"
                    aria-label={`${label} — status`}
                    value={items[key].status}
                    onChange={(e) => setStatus(key, e.target.value as ChecklistStatus)}
                  >
                    <option value="pending">Pending</option>
                    <option value="complete">Complete</option>
                    <option value="na">N/A</option>
                  </select>
                </td>
                <td>
                  <input
                    className="l360-input"
                    aria-label={`${label} — checked by`}
                    value={items[key].checked_by}
                    onChange={(e) => setItemField(key, "checked_by", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    className="l360-input"
                    type="date"
                    aria-label={`${label} — date`}
                    value={items[key].date}
                    onChange={(e) => setItemField(key, "date", e.target.value)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h4 style={{ marginBottom: 12 }}>Final approval</h4>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Input id="cl-ref" label="Educator / contractor ID" value={approval.educator_ref} onChange={(e) => setApprovalField("educator_ref", e.target.value)} />
        <Input id="cl-roles" label="Approved role(s)" value={approval.approved_roles} onChange={(e) => setApprovalField("approved_roles", e.target.value)} />
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Input id="cl-locations" label="Approved locations / modes" value={approval.approved_locations} onChange={(e) => setApprovalField("approved_locations", e.target.value)} />
        <Input id="cl-restrictions" label="Safeguarding restrictions / supervision" value={approval.sg_restrictions} onChange={(e) => setApprovalField("sg_restrictions", e.target.value)} />
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Input id="cl-start" label="Start date" type="date" value={approval.start_date} onChange={(e) => setApprovalField("start_date", e.target.value)} />
        <Input id="cl-approved-by" label="Approved by" value={approval.approved_by} onChange={(e) => setApprovalField("approved_by", e.target.value)} />
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Input id="cl-signature" label="Signature (type full name)" value={approval.signature} onChange={(e) => setApprovalField("signature", e.target.value)} />
        <Input id="cl-approval-date" label="Date" type="date" value={approval.approval_date} onChange={(e) => setApprovalField("approval_date", e.target.value)} />
      </div>
      <Button type="button" onClick={handleSave} loading={saving} loadingLabel="Saving…">
        Save checklist
      </Button>
    </Card>
  );
}

export function EducatorFormView({ userId, onClose }: { userId: number; onClose: () => void }) {
  const [form, setForm] = useState<EducatorOnboardingAdmin | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [adminName, setAdminName] = useState("");

  useEffect(() => {
    getMe().then((m) => setAdminName(m.full_name)).catch(() => {});
    adminGetEducatorOnboarding(userId)
      .then(setForm)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't load this onboarding form."))
      .finally(() => setLoaded(true));
  }, [userId]);

  async function handleSend() {
    setSending(true);
    setError(null);
    setMessage(null);
    try {
      setForm(await adminSendEducatorOnboarding(userId));
      setMessage("Onboarding form emailed to the educator.");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't send the onboarding form.");
    } finally {
      setSending(false);
    }
  }

  const a = (form?.answers ?? {}) as Record<string, unknown>;
  const submitted = form?.status === "submitted";
  const referee = (which: string) => (a[which] ?? {}) as RefereeInput;

  return (
    <div className="l360-app">
      <header className="l360-topbar">
        <Button type="button" variant="secondary" onClick={onClose}>
          ‹ Back
        </Button>
        <h1 className="l360-visually-hidden">Educator onboarding form</h1>
      </header>
      <main className="l360-content" style={{ maxWidth: 760 }}>
        {!loaded ? (
          <p className="l360-empty">Loading…</p>
        ) : error && !form ? (
          <div className="l360-alert l360-alert-danger" role="alert">⚠ {error}</div>
        ) : (
          <>
            <Card eyebrow="Onboarding" title="Status">
              {error && <div className="l360-alert l360-alert-danger" role="alert">⚠ {error}</div>}
              {message && <div className="l360-alert l360-alert-info" role="status">{message}</div>}
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
                <StatusBadge
                  variant={submitted ? "success" : "pending"}
                  label={form == null ? "Not sent yet" : submitted ? "Submitted" : "Pending"}
                />
                {form?.submitted_at && (
                  <span style={{ color: "var(--l360-bgrey)" }}>
                    Submitted {new Date(form.submitted_at).toLocaleDateString("en-GB")}
                {submitted && (
                  <a
                    className="l360-link-btn"
                    href={`/api/admin/users/${userId}/onboarding/contract`}
                  >
                    Download pre-filled contract (.docx)
                  </a>
                )}
                  </span>
                )}
                {form?.sent_at && !submitted && (
                  <span style={{ color: "var(--l360-bgrey)" }}>Sent {new Date(form.sent_at).toLocaleDateString("en-GB")}</span>
                )}
              </div>
              {!submitted && (
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <Button type="button" variant="secondary" onClick={handleSend} loading={sending} loadingLabel="Sending…">
                    {form == null || !form.sent_at ? "Email onboarding form" : "Re-send onboarding form"}
                  </Button>
                  {form?.link && (
                    <a className="l360-link-btn" href={form.link} target="_blank" rel="noopener noreferrer">Open form link</a>
                  )}
                  <Button type="button" variant="secondary" onClick={onClose}>Close</Button>
                </div>
              )}
            </Card>

            <InternalChecklist
              key={form?.id ?? "new"}
              userId={userId}
              initial={form?.internal ?? null}
              adminName={adminName}
            />

            {submitted && (
              <>
                <Card eyebrow="1 · Overview" title="Application">
                  <Rows rows={[
                    ["Role applied for", fmt(a.role_applied_for)],
                    ["Subjects / services", fmt(a.subjects_services)],
                    ["Preferred start date", fmt(a.preferred_start_date)],
                    ["Engagement type", fmt(a.engagement_type)],
                    ["Referred by", fmt(a.referred_by)],
                    ["Existing contact", fmt(a.existing_contact)],
                  ]} />
                </Card>
                <Card eyebrow="2 · Personal" title="Personal and contact details">
                  <Rows rows={[
                    ["Full legal name", fmt(a.full_legal_name)],
                    ["Preferred name", fmt(a.preferred_name)],
                    ["Former names", fmt(a.former_names)],
                    ["Date of birth", fmt(a.date_of_birth)],
                    ["ID / passport", fmt(a.id_passport_number)],
                    ["Nationality", fmt(a.nationality)],
                    ["Address", fmt(a.residential_address)],
                    ["Postcode / country", fmt(a.postcode_country)],
                    ["Mobile", fmt(a.mobile)],
                    ["Email", fmt(a.email)],
                    ["Preferred contact", fmt(a.preferred_contact)],
                    ["Right to work in Malta", fmt(a.right_to_work)],
                    ["Permit basis", fmt(a.permit_basis) + (a.permit_basis === "other" ? ` (${fmt(a.permit_basis_other)})` : "")],
                    ["Permit number / expiry", `${fmt(a.permit_number)} / ${fmt(a.permit_expiry)}`],
                  ]} />
                </Card>
                <Card eyebrow="3 · Emergency" title="Emergency contact and health">
                  <Rows rows={[
                    ["Emergency contact", `${fmt(a.emergency_name)} (${fmt(a.emergency_relationship)})`],
                    ["Phone / alternative", `${fmt(a.emergency_phone)} / ${fmt(a.emergency_alt_phone)}`],
                    ["Medical / allergy", fmt(a.medical_conditions)],
                    ["Medication / action", fmt(a.medication_action)],
                    ["Accessibility", fmt(a.accessibility_needs)],
                  ]} />
                </Card>
                <Card eyebrow="4 · Qualifications" title="Education and registration">
                  <Rows rows={[
                    ...((a.qualifications as QualificationRow[] | undefined) ?? []).map(
                      (q, i): [string, string] => [`Qualification ${i + 1}`, `${fmt(q.qualification)} — ${fmt(q.institution)}, ${fmt(q.year)} (${fmt(q.level_result)})`],
                    ),
                    ["Credentials", fmtList(a.credentials)],
                    ["Warrant / registration", `${fmt(a.warrant_number)} — ${fmt(a.issuing_body)}, expires ${fmt(a.warrant_expiry)}`],
                    ["Languages spoken", fmt(a.languages_spoken)],
                    ["Languages taught in", fmt(a.languages_taught)],
                  ]} />
                </Card>
                <Card eyebrow="5 · Experience" title="Employment and teaching experience">
                  <Rows rows={[
                    ...((a.experience as ExperienceRow[] | undefined) ?? []).map(
                      (x, i): [string, string] => [`Role ${i + 1}`, `${fmt(x.organisation)} — ${fmt(x.role_subjects)} (ages ${fmt(x.learner_ages)}, ${fmt(x.from_when)}–${fmt(x.to_when)})`],
                    ),
                    ["Experience areas", fmtList(a.experience_areas)],
                    ["Teaching profile", fmt(a.teaching_profile)],
                    ["Subjects / levels / boards", fmt(a.subjects_levels_boards)],
                    ["Inclusive learning approach", fmt(a.inclusive_approach)],
                  ]} />
                </Card>
                <Card eyebrow="6 · Digital" title="Digital skills and resources">
                  <Rows rows={[
                    ["Digital skills", fmtList(a.digital_skills)],
                    ["Own device / reliable internet", `${fmt(a.own_device)} / ${fmt(a.reliable_internet)}`],
                    ["Other software", fmt(a.other_software)],
                  ]} />
                </Card>
                <Card eyebrow="7 · Availability" title="Availability and scheduling">
                  <Rows rows={[
                    ...((a.availability as AvailabilityRow[] | undefined) ?? [])
                      .filter((d) => d.available_from || d.available_until || d.on_site || d.online)
                      .map((d): [string, string] => [
                        d.day,
                        `${fmt(d.available_from)}–${fmt(d.available_until)} (${[d.on_site && "on-site", d.online && "online"].filter(Boolean).join(", ") || "—"})`,
                      ]),
                    ["Hours weekly (min–max)", `${fmt(a.min_hours_weekly)}–${fmt(a.max_hours_weekly)}`],
                    ["School holidays", fmt(a.holidays_available)],
                    ["Notice needed", fmt(a.notice_needed)],
                    ["Unavailable dates", fmt(a.unavailable_dates)],
                    ["Preferred ages / locations", `${fmt(a.preferred_ages)} / ${fmt(a.preferred_locations)}`],
                    ["Travel", fmt(a.willing_travel) + (a.willing_travel === "within" ? ` (${fmt(a.travel_within)})` : "")],
                    ["Own transport / licence", fmt(a.own_transport)],
                  ]} />
                </Card>
                <Card eyebrow="8 · Sessions" title="Session preferences">
                  <Rows rows={[
                    ["Preferences", fmtList(a.session_preferences)],
                    ["Restrictions / notes", fmt(a.session_restrictions)],
                  ]} />
                </Card>
                <Card eyebrow="9 · Safeguarding" title="Safeguarding and suitability">
                  <Rows rows={[
                    ["Convicted / cautioned / investigated", fmt(a.sg_convicted)],
                    ["Current proceedings / inquiry / barring", fmt(a.sg_proceedings)],
                    ["Dismissed / suspended for conduct", fmt(a.sg_dismissed)],
                    ["Other relevant matters", fmt(a.sg_other_matters)],
                    ["Documents offered", fmtList(a.sg_documents)],
                    ["Clearance date / ref / renewal", `${fmt(a.clearance_date)} / ${fmt(a.clearance_reference)} / ${fmt(a.clearance_renewal)}`],
                    ["Boundaries acknowledged", [a.b_follow_procedures, a.b_report_concerns, a.b_approved_channels, a.b_no_sharing, a.b_boundaries].every(Boolean) ? "All five — yes" : "INCOMPLETE"],
                  ]} />
                </Card>
                <Card eyebrow="10 · References" title="Referees">
                  <Rows rows={(["referee1", "referee2"] as const).flatMap((which, i): [string, string][] => {
                    const r = referee(which);
                    return [
                      [`Referee ${i + 1}`, `${fmt(r.name_position)} — ${fmt(r.organisation)} (${fmt(r.relationship)}, known since ${fmt(r.known_since)})`],
                      [`Referee ${i + 1} contact`, `${fmt(r.email)} / ${fmt(r.phone)} — contact now: ${fmt(r.contact_now)}${r.contact_now === false ? `, after ${fmt(r.contact_after)}` : ""}`],
                    ];
                  }).concat([["Contact authorised", fmt(a.referee_authorisation)]])} />
                </Card>
                <Card eyebrow="11 · Payment" title="Payment and tax">
                  <Rows rows={[
                    ["Payment basis", fmt(a.payment_basis) + (a.payment_basis === "other" ? ` (${fmt(a.payment_basis_other)})` : "")],
                    ["Tax / VAT number", fmt(a.tax_vat_number)],
                    ["Social security number", fmt(a.social_security_number)],
                    ["Business name", fmt(a.business_name)],
                    ["Invoice email", fmt(a.invoice_email)],
                    ["Account holder", fmt(a.bank_account_holder)],
                    ["IBAN / BIC", `${fmt(a.iban)} / ${fmt(a.bic)}`],
                  ]} />
                </Card>
                <Card eyebrow="12–14 · Declarations" title="Policies, data protection and signature">
                  <Rows rows={[
                    ["Policies acknowledged", fmtList(a.policies_ack)],
                    ["Accuracy confirmed", fmt(a.dp_accuracy)],
                    ["Processing understood", fmt(a.dp_processing)],
                    ["Marketing opt-in", fmt(a.dp_marketing)],
                    ["Data-protection queries", fmt(a.dp_queries)],
                    ["Signed", `${fmt(form?.signature_name)}${form?.signed_date ? ` · ${new Date(form.signed_date).toLocaleDateString("en-GB")}` : ""}`],
                  ]} />
                </Card>
                <div style={{ marginTop: 16 }}>
                  <Button type="button" variant="secondary" onClick={onClose}>Close</Button>
                </div>
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
