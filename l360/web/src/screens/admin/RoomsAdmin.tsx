import { useEffect, useState, type FormEvent } from "react";
import { ConfirmButton } from "../../components/ConfirmButton";
import { Button, Card, Input, StatusBadge } from "../../ui/ui";
import {
  adminCreateRoom,
  adminDeactivateRoom,
  adminListRooms,
  adminUpdateRoom,
  type Room,
} from "../../api/client";
import { errorMessage } from "./shared";

// --- rooms ---------------------------------------------------------------

export function RoomsAdmin() {
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
                    <td><div style={{ display: "flex", gap: 8 }}>
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
                    </div></td>
                  </tr>
                ) : (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td>
                      <StatusBadge variant={r.active ? "success" : "pending"} label={r.active ? "Active" : "Inactive"} />
                    </td>
                    <td><div style={{ display: "flex", gap: 8 }}>
                      <Button type="button" variant="secondary" onClick={() => startEdit(r)}>
                        Edit
                      </Button>
                      {r.active ? (
                        <ConfirmButton
                          onConfirm={() => void toggleActive(r)}
                          confirmLabel="Really deactivate?"
                          loading={busyId === r.id}
                          loadingLabel="Saving…"
                        >
                          Deactivate
                        </ConfirmButton>
                      ) : (
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={() => toggleActive(r)}
                          loading={busyId === r.id}
                          loadingLabel="Saving…"
                        >
                          Reactivate
                        </Button>
                      )}
                    </div></td>
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
