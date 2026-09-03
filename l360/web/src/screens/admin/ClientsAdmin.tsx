import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Input, StatusBadge, Textarea } from "../../ui/ui";
import {
  adminCreateClient,
  adminListClients,
  adminUpdateClient,
  type AdminClient,
} from "../../api/client";
import { errorMessage } from "./shared";

// --- clients -----------------------------------------------------------

export function ClientsAdmin() {
  const [clients, setClients] = useState<AdminClient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const [guardianFirstName, setGuardianFirstName] = useState("");
  const [guardianSurname, setGuardianSurname] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [childName, setChildName] = useState("");
  const [childDob, setChildDob] = useState("");
  const [observations, setObservations] = useState("");
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      // Already ordered alphabetically by surname, then first name.
      setClients(await adminListClients());
    } catch (err) {
      setError(errorMessage(err, "Couldn't load learners."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!guardianFirstName.trim() || !guardianSurname.trim() || !email.trim()) {
      setFormError("Parent/guardian first name, surname and email are required.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      await adminCreateClient({
        guardian_first_name: guardianFirstName.trim(),
        guardian_surname: guardianSurname.trim(),
        email: email.trim(),
        phone: phone.trim() || null,
        child_name: childName.trim() || null,
        child_dob: childDob || null,
        observations: observations.trim() || null,
        notes: notes.trim() || null,
        active: true,
      });
      setGuardianFirstName("");
      setGuardianSurname("");
      setEmail("");
      setPhone("");
      setChildName("");
      setChildDob("");
      setObservations("");
      setNotes("");
      await refresh();
    } catch (err) {
      setFormError(errorMessage(err, "Couldn't add this learner."));
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleActive(client: AdminClient) {
    setBusyId(client.id);
    try {
      await adminUpdateClient(client.id, {
        guardian_first_name: client.guardian_first_name,
        guardian_surname: client.guardian_surname,
        email: client.email,
        phone: client.phone,
        child_name: client.child_name,
        child_dob: client.child_dob,
        observations: client.observations,
        notes: client.notes,
        active: !client.active,
      });
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't update this learner."));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card eyebrow="Directory" title="Learners">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      <h4 style={{ marginBottom: 12 }}>Add a learner</h4>
      <p style={{ color: "var(--l360-bgrey)", marginBottom: 12 }}>
        Just the basics — as soon as the learner is added, the full onboarding
        questionnaire is emailed to the parent/guardian automatically. The rest
        of their record fills itself in when they submit it (or you can complete
        it yourself from their detail page).
      </p>
      <form onSubmit={handleCreate} noValidate>
        {formError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {formError}
          </div>
        )}
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <Input
            id="new-client-first-name"
            label="Parent/guardian first name"
            required
            value={guardianFirstName}
            onChange={(e) => setGuardianFirstName(e.target.value)}
          />
          <Input
            id="new-client-surname"
            label="Parent/guardian surname"
            required
            value={guardianSurname}
            onChange={(e) => setGuardianSurname(e.target.value)}
          />
        </div>
        <Input
          id="new-client-email"
          label="Email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input id="new-client-phone" label="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <Input
            id="new-client-child-name"
            label="Child's name"
            value={childName}
            onChange={(e) => setChildName(e.target.value)}
          />
          <Input
            id="new-client-child-dob"
            label="Child's date of birth"
            type="date"
            value={childDob}
            onChange={(e) => setChildDob(e.target.value)}
          />
        </div>
        <Textarea
          id="new-client-observations"
          label="Observations"
          hint="e.g. dyslexia, Down syndrome — sensitive, admins only"
          value={observations}
          onChange={(e) => setObservations(e.target.value)}
        />
        <Textarea id="new-client-notes" label="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
        <Button type="submit" loading={submitting} loadingLabel="Adding…">
          Add learner
        </Button>
      </form>

      <h4 style={{ margin: "28px 0 12px" }}>All learners</h4>
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : clients.length === 0 ? (
        <p className="l360-empty">No learners configured yet.</p>
      ) : (
        <div style={{ overflowX: "auto", marginBottom: 20 }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Parent / Guardian</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Child's name</th>
                <th>Onboarding</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.id}>
                  <td>
                    <a href={`?client=${c.id}`} target="_blank" rel="noopener noreferrer" className="l360-link-btn">
                      {c.guardian_first_name} {c.guardian_surname}
                    </a>
                  </td>
                  <td>{c.email}</td>
                  <td>{c.phone ?? "—"}</td>
                  <td>{c.child_name ?? "—"}</td>
                  <td>
                    <StatusBadge
                      variant={c.onboarding_status === "submitted" ? "success" : c.onboarding_status === "pending" ? "info" : "pending"}
                      label={c.onboarding_status === "submitted" ? "Submitted" : c.onboarding_status === "pending" ? "Awaiting form" : "Not sent"}
                    />
                  </td>
                  <td>
                    <StatusBadge variant={c.active ? "success" : "pending"} label={c.active ? "Active" : "Inactive"} />
                  </td>
                  <td>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => toggleActive(c)}
                      loading={busyId === c.id}
                      loadingLabel="Saving…"
                    >
                      {c.active ? "Deactivate" : "Reactivate"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </Card>
  );
}
