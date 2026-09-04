import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Input, StatusBadge, Textarea } from "../ui/ui";
import {
  ApiError,
  adminGetClient,
  adminGetClientOnboarding,
  adminSendOnboarding,
  adminUpdateClient,
  type AdminClient,
  type Me,
  type OnboardingAdmin,
} from "../api/client";

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return err.status === 403 ? "Admins only — you don't have access to this page." : err.detail;
  }
  return fallback;
}

function consentLabel(v: boolean | null): string {
  return v === true ? "Yes" : v === false ? "No" : "—";
}

const CONSENT_ROWS: { key: keyof OnboardingAdmin; label: string }[] = [
  { key: "fee_undertaking", label: "Fee payment undertaking" },
  { key: "termination_60d_ack", label: "60-day payment termination policy" },
  { key: "info_storage_consent", label: "Information storage & tutor sharing" },
  { key: "marketing_opt_in", label: "Marketing opt-in" },
  { key: "epinephrine_ack", label: "Allergy medication acknowledgement" },
  { key: "accident_ack", label: "Accident liability acknowledgement" },
  { key: "cancellation_policy_ack", label: "Cancellation policy" },
  { key: "illness_policy_ack", label: "Illness policy" },
];

function OnboardingCard({ clientId }: { clientId: number }) {
  const [form, setForm] = useState<OnboardingAdmin | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminGetClientOnboarding(clientId)
      .then(setForm)
      .catch(() => setForm(null))
      .finally(() => setLoaded(true));
  }, [clientId]);

  async function handleSend() {
    setSending(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await adminSendOnboarding(clientId);
      setForm(updated);
      setMessage("Onboarding form emailed to the guardian.");
    } catch (err) {
      setError(errorMessage(err, "Couldn't send the onboarding form."));
    } finally {
      setSending(false);
    }
  }

  if (!loaded) return null;

  const submitted = form?.status === "submitted";

  return (
    <Card eyebrow="Onboarding" title="Onboarding form">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {message && (
        <div className="l360-alert l360-alert-info" role="status">
          {message}
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
        <StatusBadge
          variant={submitted ? "success" : "pending"}
          label={form == null ? "Not sent yet" : submitted ? "Submitted" : "Pending"}
        />
        {form?.sent_at && !submitted && (
          <span style={{ color: "var(--l360-bgrey)" }}>
            Sent {new Date(form.sent_at).toLocaleDateString("en-GB")}
          </span>
        )}
        {form?.submitted_at && (
          <span style={{ color: "var(--l360-bgrey)" }}>
            Submitted {new Date(form.submitted_at).toLocaleDateString("en-GB")}
            {form.source === "google_form" ? " (via the original Google Form)" : ""}
          </span>
        )}
      </div>

      {!submitted && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 12 }}>
          <Button type="button" variant="secondary" onClick={handleSend} loading={sending} loadingLabel="Sending…">
            {form == null || !form.sent_at ? "Email onboarding form" : "Re-send onboarding form"}
          </Button>
          {form?.link && (
            <a className="l360-link-btn" href={form.link} target="_blank" rel="noopener noreferrer">
              Open form link
            </a>
          )}
        </div>
      )}

      {form && submitted && (
        <div style={{ overflowX: "auto" }}>
          <table className="l360-table">
            <tbody>
              {CONSENT_ROWS.map((row) => (
                <tr key={row.key}>
                  <td>{row.label}</td>
                  <td>{consentLabel(form[row.key] as boolean | null)}</td>
                </tr>
              ))}
              <tr>
                <td>Signed</td>
                <td>
                  {form.signature_guardian1 ?? "—"}
                  {form.signature_guardian2 ? ` · ${form.signature_guardian2}` : ""}
                  {form.signed_date ? ` · ${new Date(form.signed_date).toLocaleDateString("en-GB")}` : ""}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

// Full client detail/edit page — opened in its own browser tab from a
// hyperlink on the admin Clients list (?client=<id>), rather than as a tab
// within the main app shell, since it's meant to be a focused, linkable
// view of one family's record (including sensitive onboarding notes).
export function ClientDetail({ id, me, onClose }: { id: number; me: Me | null; onClose: () => void }) {
  // A learner record opens READ-ONLY and must be unlocked before anything
  // can be changed — and only by an admin (Simon, 04/09/2026). The API is
  // admin-only already; this stops accidental edits to a live record.
  const [editing, setEditing] = useState(false);
  const isAdmin = me?.role === "admin";
  const [client, setClient] = useState<AdminClient | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [guardianFirstName, setGuardianFirstName] = useState("");
  const [guardianSurname, setGuardianSurname] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [idNumber, setIdNumber] = useState("");
  const [g2Name, setG2Name] = useState("");
  const [g2Id, setG2Id] = useState("");
  const [g2Email, setG2Email] = useState("");
  const [g2Phone, setG2Phone] = useState("");
  const [childName, setChildName] = useState("");
  const [childDob, setChildDob] = useState("");
  const [school, setSchool] = useState("");
  const [address, setAddress] = useState("");
  const [hasAllergies, setHasAllergies] = useState<"" | "yes" | "no">("");
  const [allergyDetails, setAllergyDetails] = useState("");
  const [observations, setObservations] = useState("");
  const [notes, setNotes] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  function resetFields(c: AdminClient) {
        setGuardianFirstName(c.guardian_first_name);
        setGuardianSurname(c.guardian_surname);
        setEmail(c.email);
        setPhone(c.phone ?? "");
        setIdNumber(c.guardian_id_number ?? "");
        setG2Name(c.guardian2_name ?? "");
        setG2Id(c.guardian2_id_number ?? "");
        setG2Email(c.guardian2_email ?? "");
        setG2Phone(c.guardian2_phone ?? "");
        setChildName(c.child_name ?? "");
        setChildDob(c.child_dob ?? "");
        setSchool(c.school ?? "");
        setAddress(c.address ?? "");
        setHasAllergies(c.has_allergies === true ? "yes" : c.has_allergies === false ? "no" : "");
        setAllergyDetails(c.allergy_details ?? "");
        setObservations(c.observations ?? "");
        setNotes(c.notes ?? "");
  }

  useEffect(() => {
    adminGetClient(id)
      .then((c) => {
        setClient(c);
        resetFields(c);
      })
      .catch((err) => setLoadError(errorMessage(err, "Couldn't load this learner.")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!guardianFirstName.trim() || !guardianSurname.trim() || !email.trim() || !client) {
      setSaveError("Parent/guardian first name, surname and email are required.");
      return;
    }
    setSaveError(null);
    setSaved(false);
    setSaving(true);
    try {
      const updated = await adminUpdateClient(client.id, {
        guardian_first_name: guardianFirstName.trim(),
        guardian_surname: guardianSurname.trim(),
        email: email.trim(),
        phone: phone.trim() || null,
        guardian_id_number: idNumber.trim() || null,
        guardian2_name: g2Name.trim() || null,
        guardian2_id_number: g2Id.trim() || null,
        guardian2_email: g2Email.trim() || null,
        guardian2_phone: g2Phone.trim() || null,
        child_name: childName.trim() || null,
        child_dob: childDob || null,
        school: school.trim() || null,
        address: address.trim() || null,
        has_allergies: hasAllergies === "" ? null : hasAllergies === "yes",
        allergy_details: allergyDetails.trim() || null,
        observations: observations.trim() || null,
        notes: notes.trim() || null,
        active: client.active,
      });
      setClient(updated);
      setSaved(true);
      setEditing(false);
    } catch (err) {
      setSaveError(errorMessage(err, "Couldn't save this learner."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="l360-app">
      <header className="l360-topbar">
        <span style={{ display: "inline-flex", alignItems: "center", gap: 12 }}>
          <Button type="button" variant="secondary" onClick={onClose}>
            ‹ Back
          </Button>
          <h1>Learner details</h1>
        </span>
        <span className="l360-topbar-meta">Learning 360°</span>
      </header>
      <main className="l360-content" style={{ maxWidth: 640 }}>
        {loading ? (
          <p className="l360-empty">Loading…</p>
        ) : loadError ? (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {loadError}
          </div>
        ) : (
          <>
            <Card eyebrow="Directory" title={`${client!.guardian_first_name} ${client!.guardian_surname}`}>
              <form onSubmit={handleSave} noValidate>
                {saveError && (
                  <div className="l360-alert l360-alert-danger" role="alert">
                    ⚠ {saveError}
                  </div>
                )}
                {saved && (
                  <div className="l360-alert l360-alert-info" role="status">
                    Saved.
                  </div>
                )}
                {!editing && (
                  <p className="l360-field-hint" style={{ marginTop: 0, marginBottom: 16 }}>
                    {isAdmin
                      ? "These details are locked. Unlock to edit them."
                      : "These details are read-only — an admin can change them."}
                  </p>
                )}
                <fieldset disabled={!editing} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <Input
                    id="cd-first-name"
                    label="Parent/guardian first name"
                    required
                    value={guardianFirstName}
                    onChange={(e) => setGuardianFirstName(e.target.value)}
                  />
                  <Input
                    id="cd-surname"
                    label="Parent/guardian surname"
                    required
                    value={guardianSurname}
                    onChange={(e) => setGuardianSurname(e.target.value)}
                  />
                </div>
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <Input
                    id="cd-email"
                    label="Email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                  <Input id="cd-phone" label="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
                </div>
                <Input id="cd-id-number" label="ID card number" value={idNumber} onChange={(e) => setIdNumber(e.target.value)} />

                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <Input id="cd-g2-name" label="Parent/guardian 2 — name and surname" value={g2Name} onChange={(e) => setG2Name(e.target.value)} />
                  <Input id="cd-g2-id" label="Parent/guardian 2 — ID number" value={g2Id} onChange={(e) => setG2Id(e.target.value)} />
                </div>
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <Input id="cd-g2-email" label="Parent/guardian 2 — email" type="email" value={g2Email} onChange={(e) => setG2Email(e.target.value)} />
                  <Input id="cd-g2-phone" label="Parent/guardian 2 — phone" value={g2Phone} onChange={(e) => setG2Phone(e.target.value)} />
                </div>

                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <Input
                    id="cd-child-name"
                    label="Learner's name"
                    value={childName}
                    onChange={(e) => setChildName(e.target.value)}
                  />
                  <Input
                    id="cd-child-dob"
                    label="Learner's date of birth"
                    type="date"
                    value={childDob}
                    onChange={(e) => setChildDob(e.target.value)}
                  />
                </div>
                <Input id="cd-school" label="School the learner attends" value={school} onChange={(e) => setSchool(e.target.value)} />
                <Textarea id="cd-address" label="Home address" rows={2} value={address} onChange={(e) => setAddress(e.target.value)} />

                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <div className="l360-field" style={{ flex: "0 0 160px" }}>
                    <label className="l360-field-label" htmlFor="cd-allergies">Allergies</label>
                    <select
                      id="cd-allergies"
                      className="l360-select"
                      value={hasAllergies}
                      onChange={(e) => setHasAllergies(e.target.value as "" | "yes" | "no")}
                    >
                      <option value="">Not answered</option>
                      <option value="yes">Yes</option>
                      <option value="no">No</option>
                    </select>
                  </div>
                  <div style={{ flex: 1, minWidth: 220 }}>
                    <Input
                      id="cd-allergy-details"
                      label="Allergy details"
                      hint="Health data — admins only"
                      value={allergyDetails}
                      onChange={(e) => setAllergyDetails(e.target.value)}
                    />
                  </div>
                </div>

                <Textarea
                  id="cd-observations"
                  label="Observations"
                  hint="e.g. dyslexia, Down syndrome — sensitive, admins only"
                  value={observations}
                  onChange={(e) => setObservations(e.target.value)}
                />
                <Textarea id="cd-notes" label="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
                </fieldset>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {editing ? (
                    <>
                      <Button type="submit" loading={saving} loadingLabel="Saving…">
                        Save changes
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => {
                          resetFields(client!);
                          setSaveError(null);
                          setSaved(false);
                          setEditing(false);
                        }}
                      >
                        Cancel
                      </Button>
                    </>
                  ) : (
                    isAdmin && (
                      <Button type="button" variant="secondary" onClick={() => { setSaved(false); setEditing(true); }}>
                        Unlock to edit
                      </Button>
                    )
                  )}
                  <Button type="button" variant="secondary" onClick={onClose}>
                    Close
                  </Button>
                </div>
              </form>
            </Card>
            <OnboardingCard clientId={id} />
          </>
        )}
      </main>
    </div>
  );
}
