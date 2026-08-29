import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Input, Money, Select, StatusBadge, Textarea } from "../ui/ui";
import {
  ApiError,
  adminCreateClient,
  adminCreateClosure,
  adminCreateEducatorLevel,
  adminCreateRoom,
  adminCreateServiceType,
  adminCreateUser,
  adminDeactivateRoom,
  adminDeactivateServiceType,
  adminDeactivateUser,
  adminDeleteClosure,
  adminListClients,
  adminListClosures,
  adminListEducatorLevels,
  adminListFacilityHours,
  adminListRooms,
  adminListServiceTypes,
  adminListUsers,
  adminUpdateClient,
  adminUpdateEducatorLevel,
  adminUpdateRoom,
  adminUpdateServiceType,
  adminUpdateUser,
  adminUpsertFacilityHours,
  type AdminClient,
  type AdminUser,
  type EducatorLevel,
  type FacilityClosure,
  type Room,
  type ServiceType,
  type ServiceTypeCategory,
  type UserRole,
} from "../api/client";

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return err.status === 403 ? "Admins only — you don't have access to this section." : err.detail;
  }
  return fallback;
}

const WEEKDAY_LABEL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

type TabKey = "rooms" | "levels" | "users" | "clients" | "service-types" | "hours" | "closures";

const TABS: { key: TabKey; label: string }[] = [
  { key: "rooms", label: "Rooms" },
  { key: "levels", label: "Educator levels" },
  { key: "users", label: "Users" },
  { key: "clients", label: "Learners" },
  { key: "service-types", label: "Sessions & services" },
  { key: "hours", label: "Facility hours" },
  { key: "closures", label: "Closures" },
];

// Admin: system configuration for rooms, educator levels, staff accounts,
// pricing, facility hours and closures. Tabbed sections, no router — each
// tab is its own self-contained fetch+form component.
export function Admin() {
  const [tab, setTab] = useState<TabKey>("rooms");

  return (
    <>
      <Card eyebrow="System" title="Admin">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {TABS.map((t) => (
            <Button
              key={t.key}
              type="button"
              variant={tab === t.key ? "primary" : "secondary"}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </Button>
          ))}
        </div>
      </Card>

      {tab === "rooms" && <RoomsAdmin />}
      {tab === "levels" && <LevelsAdmin />}
      {tab === "users" && <UsersAdmin />}
      {tab === "clients" && <ClientsAdmin />}
      {tab === "service-types" && <ServiceTypesAdmin />}
      {tab === "hours" && <FacilityHoursAdmin />}
      {tab === "closures" && <ClosuresAdmin />}
    </>
  );
}

// --- rooms ---------------------------------------------------------------

function RoomsAdmin() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setRooms(await adminListRooms());
    } catch (err) {
      setError(errorMessage(err, "Couldn't load rooms."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setFormError("Give the room a name.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      // Rooms are always listed alphabetically by name — no manual
      // "sort order" for admins to manage.
      await adminCreateRoom({ name: name.trim(), sort_order: 0, active: true });
      setName("");
      await refresh();
    } catch (err) {
      setFormError(errorMessage(err, "Couldn't create the room."));
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleActive(room: Room) {
    setBusyId(room.id);
    try {
      if (room.active) {
        await adminDeactivateRoom(room.id);
      } else {
        await adminUpdateRoom(room.id, { name: room.name, sort_order: room.sort_order, active: true });
      }
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't update this room."));
    } finally {
      setBusyId(null);
    }
  }

  function startEdit(room: Room) {
    setEditingId(room.id);
    setEditName(room.name);
    setError(null);
  }

  async function saveEdit(room: Room) {
    if (!editName.trim()) {
      setError("Give the room a name.");
      return;
    }
    setBusyId(room.id);
    try {
      await adminUpdateRoom(room.id, {
        name: editName.trim(),
        sort_order: room.sort_order,
        active: room.active,
      });
      setEditingId(null);
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save this room."));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card eyebrow="Facilities" title="Rooms">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : rooms.length === 0 ? (
        <p className="l360-empty">No rooms configured yet.</p>
      ) : (
        <div style={{ overflowX: "auto", marginBottom: 20 }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Room</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((r) =>
                editingId === r.id ? (
                  <tr key={r.id}>
                    <td>
                      <input
                        className="l360-input"
                        aria-label="Room name"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                      />
                    </td>
                    <td>
                      <StatusBadge variant={r.active ? "success" : "pending"} label={r.active ? "Active" : "Inactive"} />
                    </td>
                    <td style={{ display: "flex", gap: 8 }}>
                      <Button
                        type="button"
                        onClick={() => saveEdit(r)}
                        loading={busyId === r.id}
                        loadingLabel="Saving…"
                      >
                        Save
                      </Button>
                      <Button type="button" variant="secondary" onClick={() => setEditingId(null)}>
                        Cancel
                      </Button>
                    </td>
                  </tr>
                ) : (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td>
                      <StatusBadge variant={r.active ? "success" : "pending"} label={r.active ? "Active" : "Inactive"} />
                    </td>
                    <td style={{ display: "flex", gap: 8 }}>
                      <Button type="button" variant="secondary" onClick={() => startEdit(r)}>
                        Edit
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => toggleActive(r)}
                        loading={busyId === r.id}
                        loadingLabel="Saving…"
                      >
                        {r.active ? "Deactivate" : "Reactivate"}
                      </Button>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}

      <h4 style={{ marginBottom: 12 }}>Add a room</h4>
      <form onSubmit={handleCreate} noValidate>
        {formError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {formError}
          </div>
        )}
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
          <Input id="new-room-name" label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
          <div style={{ marginBottom: 16 }}>
            <Button type="submit" loading={submitting} loadingLabel="Adding…">
              Add room
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}

// --- educator levels -------------------------------------------------------

function LevelsAdmin() {
  const [levels, setLevels] = useState<EducatorLevel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setLevels(await adminListEducatorLevels());
    } catch (err) {
      setError(errorMessage(err, "Couldn't load educator levels."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setFormError("Give the level a name.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      await adminCreateEducatorLevel({ name: name.trim(), sort_order: Number(sortOrder) || 0, active: true });
      setName("");
      setSortOrder("0");
      await refresh();
    } catch (err) {
      setFormError(errorMessage(err, "Couldn't create the level."));
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleActive(level: EducatorLevel) {
    setBusyId(level.id);
    try {
      await adminUpdateEducatorLevel(level.id, {
        name: level.name,
        sort_order: level.sort_order,
        active: !level.active,
      });
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't update this level."));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card eyebrow="Staffing" title="Educator levels">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : levels.length === 0 ? (
        <p className="l360-empty">No educator levels configured yet.</p>
      ) : (
        <div style={{ overflowX: "auto", marginBottom: 20 }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Level</th>
                <th>Sort order</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {levels.map((l) => (
                <tr key={l.id}>
                  <td>{l.name}</td>
                  <td className="l360-mono">{l.sort_order}</td>
                  <td>
                    <StatusBadge variant={l.active ? "success" : "pending"} label={l.active ? "Active" : "Inactive"} />
                  </td>
                  <td>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => toggleActive(l)}
                      loading={busyId === l.id}
                      loadingLabel="Saving…"
                    >
                      {l.active ? "Deactivate" : "Reactivate"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h4 style={{ marginBottom: 12 }}>Add a level</h4>
      <form onSubmit={handleCreate} noValidate>
        {formError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {formError}
          </div>
        )}
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
          <Input id="new-level-name" label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
          <Input
            id="new-level-sort"
            label="Sort order"
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
          />
          <div style={{ marginBottom: 16 }}>
            <Button type="submit" loading={submitting} loadingLabel="Adding…">
              Add level
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}

// --- users -----------------------------------------------------------------

function UsersAdmin() {
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
    <Card eyebrow="Staffing" title="Users">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
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

      <h4 style={{ marginBottom: 12 }}>Add a user</h4>
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
          Add user
        </Button>
      </form>
    </Card>
  );
}

// --- clients -----------------------------------------------------------

function ClientsAdmin() {
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
    </Card>
  );
}

// --- service types (named sessions/additional services) --------------------

const CATEGORY_OPTIONS: { value: ServiceTypeCategory; label: string }[] = [
  { value: "session", label: "Session" },
  { value: "additional_service", label: "Additional service" },
];

interface ServiceTypeDraft {
  name: string;
  client_price: string;
  tutor_payment: string;
  requires_room: boolean;
}

function ServiceTypesAdmin() {
  const [serviceTypes, setServiceTypes] = useState<ServiceType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<ServiceTypeDraft>({
    name: "", client_price: "", tutor_payment: "", requires_room: true,
  });

  const [name, setName] = useState("");
  const [category, setCategory] = useState<ServiceTypeCategory>("session");
  const [clientPrice, setClientPrice] = useState("");
  const [tutorPayment, setTutorPayment] = useState("");
  const [requiresRoom, setRequiresRoom] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setServiceTypes(await adminListServiceTypes());
    } catch (err) {
      setError(errorMessage(err, "Couldn't load sessions & services."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !clientPrice || !tutorPayment) {
      setFormError("Give it a name and both prices.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      await adminCreateServiceType({
        name: name.trim(),
        category,
        client_price_cents: Math.round(Number(clientPrice) * 100),
        tutor_payment_cents: Math.round(Number(tutorPayment) * 100),
        requires_room: category === "session" ? requiresRoom : false,
        sort_order: 0,
        active: true,
      });
      setName("");
      setClientPrice("");
      setTutorPayment("");
      setRequiresRoom(true);
      await refresh();
    } catch (err) {
      setFormError(errorMessage(err, "Couldn't add this."));
    } finally {
      setSubmitting(false);
    }
  }

  function startEdit(row: ServiceType) {
    setEditingId(row.id);
    setEditDraft({
      name: row.name,
      client_price: (row.client_price_cents / 100).toFixed(2),
      tutor_payment: (row.tutor_payment_cents / 100).toFixed(2),
      requires_room: row.requires_room,
    });
    setError(null);
  }

  async function saveEdit(row: ServiceType) {
    if (!editDraft.name.trim() || !editDraft.client_price || !editDraft.tutor_payment) {
      setError("Give it a name and both prices.");
      return;
    }
    setBusyId(row.id);
    try {
      await adminUpdateServiceType(row.id, {
        name: editDraft.name.trim(),
        category: row.category,
        client_price_cents: Math.round(Number(editDraft.client_price) * 100),
        tutor_payment_cents: Math.round(Number(editDraft.tutor_payment) * 100),
        requires_room: row.category === "session" ? editDraft.requires_room : false,
        sort_order: row.sort_order,
        active: row.active,
      });
      setEditingId(null);
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save this."));
    } finally {
      setBusyId(null);
    }
  }

  async function toggleActive(row: ServiceType) {
    setBusyId(row.id);
    try {
      if (row.active) {
        await adminDeactivateServiceType(row.id);
      } else {
        await adminUpdateServiceType(row.id, {
          name: row.name,
          category: row.category,
          client_price_cents: row.client_price_cents,
          tutor_payment_cents: row.tutor_payment_cents,
          requires_room: row.requires_room,
          sort_order: row.sort_order,
          active: true,
        });
      }
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't update this."));
    } finally {
      setBusyId(null);
    }
  }

  function renderTable(rows: ServiceType[], emptyLabel: string, showRoomColumn: boolean) {
    if (rows.length === 0) return <p className="l360-empty">{emptyLabel}</p>;
    return (
      <div style={{ overflowX: "auto", marginBottom: 20 }}>
        <table className="l360-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Learner price</th>
              <th>Tutor payment</th>
              {showRoomColumn && <th>Needs a room?</th>}
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) =>
              editingId === r.id ? (
                <tr key={r.id}>
                  <td>
                    <input
                      className="l360-input"
                      aria-label="Name"
                      value={editDraft.name}
                      onChange={(e) => setEditDraft((d) => ({ ...d, name: e.target.value }))}
                    />
                  </td>
                  <td>
                    <input
                      className="l360-input"
                      type="number"
                      step="0.01"
                      min="0"
                      aria-label="Learner price (€)"
                      value={editDraft.client_price}
                      onChange={(e) => setEditDraft((d) => ({ ...d, client_price: e.target.value }))}
                    />
                  </td>
                  <td>
                    <input
                      className="l360-input"
                      type="number"
                      step="0.01"
                      min="0"
                      aria-label="Tutor payment (€)"
                      value={editDraft.tutor_payment}
                      onChange={(e) => setEditDraft((d) => ({ ...d, tutor_payment: e.target.value }))}
                    />
                  </td>
                  {showRoomColumn && (
                    <td>
                      <input
                        type="checkbox"
                        aria-label="Needs a room?"
                        checked={editDraft.requires_room}
                        onChange={(e) => setEditDraft((d) => ({ ...d, requires_room: e.target.checked }))}
                      />
                    </td>
                  )}
                  <td>
                    <StatusBadge variant={r.active ? "success" : "pending"} label={r.active ? "Active" : "Inactive"} />
                  </td>
                  <td style={{ display: "flex", gap: 8 }}>
                    <Button type="button" onClick={() => saveEdit(r)} loading={busyId === r.id} loadingLabel="Saving…">
                      Save
                    </Button>
                    <Button type="button" variant="secondary" onClick={() => setEditingId(null)}>
                      Cancel
                    </Button>
                  </td>
                </tr>
              ) : (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td><Money cents={r.client_price_cents} /></td>
                  <td><Money cents={r.tutor_payment_cents} /></td>
                  {showRoomColumn && <td>{r.requires_room ? "Yes" : "No"}</td>}
                  <td>
                    <StatusBadge variant={r.active ? "success" : "pending"} label={r.active ? "Active" : "Inactive"} />
                  </td>
                  <td style={{ display: "flex", gap: 8 }}>
                    <Button type="button" variant="secondary" onClick={() => startEdit(r)}>
                      Edit
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => toggleActive(r)}
                      loading={busyId === r.id}
                      loadingLabel="Saving…"
                    >
                      {r.active ? "Deactivate" : "Reactivate"}
                    </Button>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
    );
  }

  const sessions = serviceTypes.filter((s) => s.category === "session");
  const additionalServices = serviceTypes.filter((s) => s.category === "additional_service");

  return (
    <Card eyebrow="Finance" title="Sessions & services">
      <p className="l360-field-hint" style={{ marginBottom: 16 }}>
        Named prices from the foundation's price list that don't fit the level+duration model above —
        meetings, programmes and group sessions, plus one-off additional services like flashcards.
      </p>
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : (
        <>
          <h4 style={{ marginBottom: 12 }}>Sessions</h4>
          {renderTable(sessions, "No sessions configured yet.", true)}

          <h4 style={{ marginBottom: 12 }}>Additional services</h4>
          {renderTable(additionalServices, "No additional services configured yet.", false)}
        </>
      )}

      <h4 style={{ marginBottom: 12 }}>Add a session or service</h4>
      <form onSubmit={handleCreate} noValidate>
        {formError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {formError}
          </div>
        )}
        <Input id="new-service-type-name" label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
        <Select
          id="new-service-type-category"
          label="Category"
          required
          value={category}
          onChange={(e) => setCategory(e.target.value as ServiceTypeCategory)}
          options={CATEGORY_OPTIONS}
        />
        <Input
          id="new-service-type-client-price"
          label="Learner price (€)"
          type="number"
          step="0.01"
          min="0"
          required
          value={clientPrice}
          onChange={(e) => setClientPrice(e.target.value)}
        />
        <Input
          id="new-service-type-tutor-payment"
          label="Tutor payment (€)"
          type="number"
          step="0.01"
          min="0"
          required
          value={tutorPayment}
          onChange={(e) => setTutorPayment(e.target.value)}
        />
        {category === "session" && (
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <input
              type="checkbox"
              checked={requiresRoom}
              onChange={(e) => setRequiresRoom(e.target.checked)}
            />
            Needs a room (unlike home/school visits)
          </label>
        )}
        <Button type="submit" loading={submitting} loadingLabel="Adding…">
          Add
        </Button>
      </form>
    </Card>
  );
}

// --- facility hours ----------------------------------------------------

function timeToInput(t: string): string {
  return t.slice(0, 5);
}

function timeToApi(t: string): string {
  return t.length === 5 ? `${t}:00` : t;
}

function FacilityHoursAdmin() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<number, { open: string; close: string }>>({});
  const [busyDay, setBusyDay] = useState<number | null>(null);
  // Per-day, not a single value — saving one day must not clear the
  // "Saved" confirmation off every other day that was already saved.
  const [savedDays, setSavedDays] = useState<Set<number>>(new Set());

  function editDraft(weekday: number, field: "open" | "close", value: string) {
    setDrafts((d) => ({ ...d, [weekday]: { ...d[weekday], [field]: value } }));
    setSavedDays((prev) => {
      if (!prev.has(weekday)) return prev;
      const next = new Set(prev);
      next.delete(weekday);
      return next;
    });
  }

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const hours = await adminListFacilityHours();
      const map = new Map(hours.map((h) => [h.weekday, h] as const));
      const nextDrafts: Record<number, { open: string; close: string }> = {};
      for (let d = 0; d < 7; d++) {
        const existing = map.get(d);
        nextDrafts[d] = {
          open: existing ? timeToInput(existing.open_time) : "09:00",
          close: existing ? timeToInput(existing.close_time) : "17:00",
        };
      }
      setDrafts(nextDrafts);
    } catch (err) {
      setError(errorMessage(err, "Couldn't load facility hours."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleSave(weekday: number) {
    const draft = drafts[weekday];
    if (!draft) return;
    setBusyDay(weekday);
    setError(null);
    try {
      await adminUpsertFacilityHours({
        weekday,
        open_time: timeToApi(draft.open),
        close_time: timeToApi(draft.close),
      });
      setSavedDays((prev) => new Set(prev).add(weekday));
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save these hours."));
    } finally {
      setBusyDay(null);
    }
  }

  return (
    <Card eyebrow="Facilities" title="Facility hours">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Day</th>
                <th>Open</th>
                <th>Close</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {WEEKDAY_LABEL.map((label, weekday) => {
                const draft = drafts[weekday] ?? { open: "09:00", close: "17:00" };
                return (
                  <tr key={weekday}>
                    <td>{label}</td>
                    <td>
                      <input
                        className="l360-input"
                        type="time"
                        aria-label={`${label} open time`}
                        value={draft.open}
                        onChange={(e) => editDraft(weekday, "open", e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        className="l360-input"
                        type="time"
                        aria-label={`${label} close time`}
                        value={draft.close}
                        onChange={(e) => editDraft(weekday, "close", e.target.value)}
                      />
                    </td>
                    <td>
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => handleSave(weekday)}
                        loading={busyDay === weekday}
                        loadingLabel="Saving…"
                      >
                        {savedDays.has(weekday) ? "Saved" : "Save"}
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

// --- closures ------------------------------------------------------------

function ClosuresAdmin() {
  const [closures, setClosures] = useState<FacilityClosure[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const [date, setDate] = useState("");
  const [reason, setReason] = useState("");
  const [roomId, setRoomId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [c, r] = await Promise.all([adminListClosures(), adminListRooms()]);
      setClosures(c);
      setRooms(r);
    } catch (err) {
      setError(errorMessage(err, "Couldn't load closures."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function roomName(id: number | null): string {
    if (id === null) return "All rooms";
    return rooms.find((r) => r.id === id)?.name ?? `#${id}`;
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!date || !reason.trim()) {
      setFormError("Give the closure a date and a reason.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      await adminCreateClosure({ date, reason: reason.trim(), room_id: roomId ? Number(roomId) : null });
      setDate("");
      setReason("");
      setRoomId("");
      await refresh();
    } catch (err) {
      setFormError(errorMessage(err, "Couldn't add this closure."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    setBusyId(id);
    setError(null);
    try {
      await adminDeleteClosure(id);
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't remove this closure."));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card eyebrow="Facilities" title="Closures">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : closures.length === 0 ? (
        <p className="l360-empty">No closures scheduled.</p>
      ) : (
        <div style={{ overflowX: "auto", marginBottom: 20 }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Reason</th>
                <th>Room</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {closures.map((c) => (
                <tr key={c.id}>
                  <td className="l360-mono">{c.date}</td>
                  <td>{c.reason}</td>
                  <td>{roomName(c.room_id)}</td>
                  <td>
                    <Button
                      type="button"
                      variant="destructive"
                      onClick={() => handleDelete(c.id)}
                      loading={busyId === c.id}
                      loadingLabel="Removing…"
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h4 style={{ marginBottom: 12 }}>Add a closure</h4>
      <form onSubmit={handleCreate} noValidate>
        {formError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {formError}
          </div>
        )}
        <Input id="new-closure-date" label="Date" type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
        <Input
          id="new-closure-reason"
          label="Reason"
          required
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <Select
          id="new-closure-room"
          label="Room"
          hint="Leave blank to close the whole facility"
          placeholder="All rooms"
          value={roomId}
          onChange={(e) => setRoomId(e.target.value)}
          options={rooms.map((r) => ({ value: String(r.id), label: r.name }))}
        />
        <Button type="submit" loading={submitting} loadingLabel="Adding…">
          Add closure
        </Button>
      </form>
    </Card>
  );
}
