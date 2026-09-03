import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Input, Select, StatusBadge } from "../../ui/ui";
import {
  adminCreateUser,
  adminDeactivateUser,
  adminListEducatorLevels,
  adminListUsers,
  adminUpdateUser,
  type AdminUser,
  type EducatorLevel,
  type UserRole,
} from "../../api/client";
import { errorMessage } from "./shared";

// --- users -----------------------------------------------------------------

// Onboarding-form cell for the Users table: educators link through to the
// read-only form view (?educator-form=<id>), which also hosts send/re-send.
function UserOnboardingCell({ user }: { user: AdminUser }) {
  if (user.role !== "educator") return <>—</>;
  const status = user.onboarding_status;
  return (
    <a href={`?educator-form=${user.id}`} target="_blank" rel="noopener noreferrer" className="l360-link-btn">
      <StatusBadge
        variant={status === "submitted" ? "success" : status === "pending" ? "info" : "pending"}
        label={status === "submitted" ? "Submitted" : status === "pending" ? "Awaiting form" : "Not sent"}
      />
    </a>
  );
}

export function UsersAdmin() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [levels, setLevels] = useState<EducatorLevel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRole>("educator");
  const [levelId, setLevelId] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // "Add educator" opens the form in a modal (Simon, 04/09/2026 — same
  // pattern as Learners); the list sits below under its own heading.
  const [showAdd, setShowAdd] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editLevelId, setEditLevelId] = useState("");

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [u, l] = await Promise.all([adminListUsers(), adminListEducatorLevels()]);
      setUsers(u);
      setLevels(l);
    } catch (err) {
      setError(errorMessage(err, "Couldn't load users."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function levelName(id: number | null): string {
    if (id === null) return "—";
    return levels.find((l) => l.id === id)?.name ?? `#${id}`;
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!email.trim() || !fullName.trim() || password.length < 8) {
      setFormError("Email, full name and a password of at least 8 characters are required.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      await adminCreateUser({
        email: email.trim(),
        full_name: fullName.trim(),
        role,
        level_id: levelId ? Number(levelId) : null,
        password,
      });
      setEmail("");
      setFullName("");
      setRole("educator");
      setLevelId("");
      setPassword("");
      setShowAdd(false);
      await refresh();
    } catch (err) {
      setFormError(errorMessage(err, "Couldn't create this user."));
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleActive(user: AdminUser) {
    setBusyId(user.id);
    try {
      if (user.active) {
        await adminDeactivateUser(user.id);
      } else {
        await adminUpdateUser(user.id, { active: true });
      }
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't update this user."));
    } finally {
      setBusyId(null);
    }
  }

  function startEditLevel(user: AdminUser) {
    setEditingId(user.id);
    setEditLevelId(user.level_id ? String(user.level_id) : "");
    setError(null);
  }

  async function saveLevel(user: AdminUser) {
    setBusyId(user.id);
    try {
      // Anyone — admin or educator — can be given a level, which is what
      // makes them bookable as an educator (e.g. a founder who also
      // delivers sessions).
      await adminUpdateUser(user.id, { level_id: editLevelId ? Number(editLevelId) : null });
      setEditingId(null);
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't update this user."));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card eyebrow="Staffing" title="Educators">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      <div style={{ marginBottom: 16 }}>
        <Button type="button" onClick={() => setShowAdd(true)}>
          Add educator
        </Button>
      </div>

      {showAdd && (
        <div className="l360-modal-backdrop" onClick={() => setShowAdd(false)}>
          <div className="l360-modal-card" onClick={(e) => e.stopPropagation()}>
            <Card eyebrow="Staffing" title="Add educator">
              <p className="l360-field-hint" style={{ marginTop: 0, marginBottom: 12 }}>
                New educators are automatically emailed the educator onboarding form
                (qualifications, availability, safeguarding declarations, referees,
                payment details) as soon as the account is created. Choose the Admin
                role for office staff.
              </p>
            <form onSubmit={handleCreate} noValidate>
              {formError && (
                <div className="l360-alert l360-alert-danger" role="alert">
                  ⚠ {formError}
                </div>
              )}
              <Input id="new-user-email" label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
              <Input id="new-user-name" label="Full name" required value={fullName} onChange={(e) => setFullName(e.target.value)} />
              <Select
                id="new-user-role"
                label="Role"
                required
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                options={[
                  { value: "educator", label: "Educator" },
                  { value: "admin", label: "Admin" },
                ]}
              />
              <Select
                id="new-user-level"
                label="Level"
                hint={role === "admin" ? "Optional — only set this if they also deliver sessions" : undefined}
                placeholder="No level"
                value={levelId}
                onChange={(e) => setLevelId(e.target.value)}
                options={levels.map((l) => ({ value: String(l.id), label: l.name }))}
              />
              <Input
                id="new-user-password"
                label="Password"
                type="password"
                hint="At least 8 characters"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <Button type="submit" loading={submitting} loadingLabel="Adding…">
                Add educator
              </Button>
            </form>
              <div style={{ marginTop: 8 }}>
                <Button type="button" variant="secondary" onClick={() => setShowAdd(false)} disabled={submitting}>
                  Close
                </Button>
              </div>
            </Card>
          </div>
        </div>
      )}

      <h4 style={{ margin: "8px 0 12px" }}>All educators &amp; admins</h4>
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : users.length === 0 ? (
        <p className="l360-empty">No users configured yet.</p>
      ) : (
        <div style={{ overflowX: "auto", marginBottom: 20 }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Level</th>
                <th>Onboarding</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) =>
                editingId === u.id ? (
                  <tr key={u.id}>
                    <td>{u.full_name}</td>
                    <td>{u.email}</td>
                    <td style={{ textTransform: "capitalize" }}>{u.role}</td>
                    <td>
                      <select
                        className="l360-select"
                        aria-label="Level"
                        value={editLevelId}
                        onChange={(e) => setEditLevelId(e.target.value)}
                      >
                        <option value="">No level</option>
                        {levels.map((l) => (
                          <option key={l.id} value={String(l.id)}>{l.name}</option>
                        ))}
                      </select>
                    </td>
                    <td><UserOnboardingCell user={u} /></td>
                    <td>
                      <StatusBadge variant={u.active ? "success" : "pending"} label={u.active ? "Active" : "Inactive"} />
                    </td>
                    <td style={{ display: "flex", gap: 8 }}>
                      <Button type="button" onClick={() => saveLevel(u)} loading={busyId === u.id} loadingLabel="Saving…">
                        Save
                      </Button>
                      <Button type="button" variant="secondary" onClick={() => setEditingId(null)}>
                        Cancel
                      </Button>
                    </td>
                  </tr>
                ) : (
                  <tr key={u.id}>
                    <td>{u.full_name}</td>
                    <td>{u.email}</td>
                    <td style={{ textTransform: "capitalize" }}>{u.role}</td>
                    <td>{levelName(u.level_id)}</td>
                    <td><UserOnboardingCell user={u} /></td>
                    <td>
                      <StatusBadge variant={u.active ? "success" : "pending"} label={u.active ? "Active" : "Inactive"} />
                    </td>
                    <td style={{ display: "flex", gap: 8 }}>
                      <Button type="button" variant="secondary" onClick={() => startEditLevel(u)}>
                        Edit level
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => toggleActive(u)}
                        loading={busyId === u.id}
                        loadingLabel="Saving…"
                      >
                        {u.active ? "Deactivate" : "Reactivate"}
                      </Button>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}

    </Card>
  );
}
