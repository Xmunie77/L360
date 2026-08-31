import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Input, Select } from "../../ui/ui";
import {
  adminCreateClosure,
  adminDeleteClosure,
  adminListClosures,
  adminListRooms,
  type FacilityClosure,
  type Room,
} from "../../api/client";
import { errorMessage } from "./shared";

// --- closures ------------------------------------------------------------

export function ClosuresAdmin() {
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
