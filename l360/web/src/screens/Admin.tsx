import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Input, Money, Select, StatusBadge } from "../ui/ui";
import {
  ApiError,
  adminCreateClosure,
  adminCreateEducatorLevel,
  adminCreatePriceEntry,
  adminCreateRoom,
  adminCreateUser,
  adminDeactivateRoom,
  adminDeactivateUser,
  adminDeleteClosure,
  adminListClosures,
  adminListEducatorLevels,
  adminListFacilityHours,
  adminListPriceList,
  adminListRooms,
  adminListUsers,
  adminUpdateEducatorLevel,
  adminUpdateRoom,
  adminUpdateUser,
  adminUpsertFacilityHours,
  type AdminUser,
  type Duration,
  type EducatorLevel,
  type FacilityClosure,
  type PriceListEntry,
  type Room,
  type UserRole,
} from "../api/client";

// Note on scope: Clients admin CRUD is intentionally left out — Clients.tsx
// already gives staff a read-only directory, and client create/edit wasn't
// worth the extra surface area for this pass. Every other admin section
// listed in the brief is here.

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return err.status === 403 ? "Admins only — you don't have access to this section." : err.detail;
  }
  return fallback;
}

const WEEKDAY_LABEL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const DURATION_OPTIONS = [
  { value: "60", label: "60 minutes" },
  { value: "90", label: "90 minutes" },
  { value: "120", label: "120 minutes" },
];

type TabKey = "rooms" | "levels" | "users" | "price-list" | "hours" | "closures";

const TABS: { key: TabKey; label: string }[] = [
  { key: "rooms", label: "Rooms" },
  { key: "levels", label: "Educator levels" },
  { key: "users", label: "Users" },
  { key: "price-list", label: "Price list" },
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
      {tab === "price-list" && <PriceListAdmin />}
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
  const [sortOrder, setSortOrder] = useState("0");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

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
      await adminCreateRoom({ name: name.trim(), sort_order: Number(sortOrder) || 0, active: true });
      setName("");
      setSortOrder("0");
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
                <th>Sort order</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((r) => (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td className="l360-mono">{r.sort_order}</td>
                  <td>
                    <StatusBadge variant={r.active ? "success" : "pending"} label={r.active ? "Active" : "Inactive"} />
                  </td>
                  <td>
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
              ))}
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
          <Input
            id="new-room-sort"
            label="Sort order"
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
          />
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
        level_id: role === "educator" && levelId ? Number(levelId) : null,
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
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.full_name}</td>
                  <td>{u.email}</td>
                  <td style={{ textTransform: "capitalize" }}>{u.role}</td>
                  <td>{u.role === "educator" ? levelName(u.level_id) : "—"}</td>
                  <td>
                    <StatusBadge variant={u.active ? "success" : "pending"} label={u.active ? "Active" : "Inactive"} />
                  </td>
                  <td>
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
              ))}
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
        {role === "educator" && (
          <Select
            id="new-user-level"
            label="Level"
            placeholder="Choose a level"
            value={levelId}
            onChange={(e) => setLevelId(e.target.value)}
            options={levels.map((l) => ({ value: String(l.id), label: l.name }))}
          />
        )}
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

// --- price list ------------------------------------------------------------

function PriceListAdmin() {
  const [entries, setEntries] = useState<PriceListEntry[]>([]);
  const [levels, setLevels] = useState<EducatorLevel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [levelId, setLevelId] = useState("");
  const [duration, setDuration] = useState("60");
  const [clientPrice, setClientPrice] = useState("");
  const [educatorRate, setEducatorRate] = useState("");
  const [validFrom, setValidFrom] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [p, l] = await Promise.all([adminListPriceList(), adminListEducatorLevels()]);
      setEntries(p);
      setLevels(l);
    } catch (err) {
      setError(errorMessage(err, "Couldn't load the price list."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function levelName(id: number): string {
    return levels.find((l) => l.id === id)?.name ?? `#${id}`;
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!levelId || !clientPrice || !educatorRate || !validFrom) {
      setFormError("Fill in level, both prices and an effective date.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      await adminCreatePriceEntry({
        level_id: Number(levelId),
        duration_minutes: Number(duration) as Duration,
        client_price_cents: Math.round(Number(clientPrice) * 100),
        educator_rate_cents: Math.round(Number(educatorRate) * 100),
        valid_from: validFrom,
      });
      setClientPrice("");
      setEducatorRate("");
      setValidFrom("");
      await refresh();
    } catch (err) {
      setFormError(errorMessage(err, "Couldn't add this price."));
    } finally {
      setSubmitting(false);
    }
  }

  const sorted = [...entries].sort((a, b) =>
    a.level_id !== b.level_id
      ? a.level_id - b.level_id
      : a.duration_minutes !== b.duration_minutes
        ? a.duration_minutes - b.duration_minutes
        : a.valid_from.localeCompare(b.valid_from),
  );

  return (
    <Card eyebrow="Finance" title="Price list">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : sorted.length === 0 ? (
        <p className="l360-empty">No prices configured yet.</p>
      ) : (
        <div style={{ overflowX: "auto", marginBottom: 20 }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Level</th>
                <th>Duration</th>
                <th>Client price</th>
                <th>Educator rate</th>
                <th>Effective from</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((p) => (
                <tr key={p.id}>
                  <td>{levelName(p.level_id)}</td>
                  <td>{p.duration_minutes} min</td>
                  <td><Money cents={p.client_price_cents} /></td>
                  <td><Money cents={p.educator_rate_cents} /></td>
                  <td className="l360-mono">{p.valid_from}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h4 style={{ marginBottom: 4 }}>Add a new rate</h4>
      <p className="l360-field-hint" style={{ marginBottom: 12 }}>
        This adds a new price effective from the date below — it doesn't edit history. Earlier rates
        stay on past invoices.
      </p>
      <form onSubmit={handleCreate} noValidate>
        {formError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {formError}
          </div>
        )}
        <Select
          id="new-price-level"
          label="Level"
          required
          placeholder="Choose a level"
          value={levelId}
          onChange={(e) => setLevelId(e.target.value)}
          options={levels.map((l) => ({ value: String(l.id), label: l.name }))}
        />
        <Select
          id="new-price-duration"
          label="Duration"
          required
          value={duration}
          onChange={(e) => setDuration(e.target.value)}
          options={DURATION_OPTIONS}
        />
        <Input
          id="new-price-client"
          label="Client price (€)"
          type="number"
          step="0.01"
          min="0"
          required
          value={clientPrice}
          onChange={(e) => setClientPrice(e.target.value)}
        />
        <Input
          id="new-price-educator"
          label="Educator rate (€)"
          type="number"
          step="0.01"
          min="0"
          required
          value={educatorRate}
          onChange={(e) => setEducatorRate(e.target.value)}
        />
        <Input
          id="new-price-valid-from"
          label="Effective from"
          type="date"
          required
          value={validFrom}
          onChange={(e) => setValidFrom(e.target.value)}
        />
        <Button type="submit" loading={submitting} loadingLabel="Adding…">
          Add rate
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
  const [savedDay, setSavedDay] = useState<number | null>(null);

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
    setSavedDay(null);
    setError(null);
    try {
      await adminUpsertFacilityHours({
        weekday,
        open_time: timeToApi(draft.open),
        close_time: timeToApi(draft.close),
      });
      setSavedDay(weekday);
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
                        onChange={(e) =>
                          setDrafts((d) => ({ ...d, [weekday]: { ...d[weekday], open: e.target.value } }))
                        }
                      />
                    </td>
                    <td>
                      <input
                        className="l360-input"
                        type="time"
                        aria-label={`${label} close time`}
                        value={draft.close}
                        onChange={(e) =>
                          setDrafts((d) => ({ ...d, [weekday]: { ...d[weekday], close: e.target.value } }))
                        }
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
                        {savedDay === weekday ? "Saved" : "Save"}
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
