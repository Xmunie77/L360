import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Input, Textarea } from "../ui/ui";
import { ApiError, adminGetClient, adminUpdateClient, type AdminClient } from "../api/client";

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return err.status === 403 ? "Admins only — you don't have access to this page." : err.detail;
  }
  return fallback;
}

// Full client detail/edit page — opened in its own browser tab from a
// hyperlink on the admin Clients list (?client=<id>), rather than as a tab
// within the main app shell, since it's meant to be a focused, linkable
// view of one family's record (including sensitive onboarding notes).
export function ClientDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const [client, setClient] = useState<AdminClient | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [guardianFirstName, setGuardianFirstName] = useState("");
  const [guardianSurname, setGuardianSurname] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [childName, setChildName] = useState("");
  const [childDob, setChildDob] = useState("");
  const [observations, setObservations] = useState("");
  const [notes, setNotes] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    adminGetClient(id)
      .then((c) => {
        setClient(c);
        setGuardianFirstName(c.guardian_first_name);
        setGuardianSurname(c.guardian_surname);
        setEmail(c.email);
        setPhone(c.phone ?? "");
        setChildName(c.child_name ?? "");
        setChildDob(c.child_dob ?? "");
        setObservations(c.observations ?? "");
        setNotes(c.notes ?? "");
      })
      .catch((err) => setLoadError(errorMessage(err, "Couldn't load this learner.")))
      .finally(() => setLoading(false));
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
        child_name: childName.trim() || null,
        child_dob: childDob || null,
        observations: observations.trim() || null,
        notes: notes.trim() || null,
        active: client.active,
      });
      setClient(updated);
      setSaved(true);
    } catch (err) {
      setSaveError(errorMessage(err, "Couldn't save this learner."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="l360-app">
      <header className="l360-topbar">
        <h1>Learner details</h1>
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
              <Input
                id="cd-email"
                label="Email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <Input id="cd-phone" label="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                <Input
                  id="cd-child-name"
                  label="Child's name"
                  value={childName}
                  onChange={(e) => setChildName(e.target.value)}
                />
                <Input
                  id="cd-child-dob"
                  label="Child's date of birth"
                  type="date"
                  value={childDob}
                  onChange={(e) => setChildDob(e.target.value)}
                />
              </div>
              <Textarea
                id="cd-observations"
                label="Observations"
                hint="e.g. dyslexia, Down syndrome — sensitive, admins only"
                value={observations}
                onChange={(e) => setObservations(e.target.value)}
              />
              <Textarea id="cd-notes" label="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
              <div style={{ display: "flex", gap: 8 }}>
                <Button type="submit" loading={saving} loadingLabel="Saving…">
                  Save
                </Button>
                <Button type="button" variant="secondary" onClick={onClose}>
                  Close
                </Button>
              </div>
            </form>
          </Card>
        )}
      </main>
    </div>
  );
}
