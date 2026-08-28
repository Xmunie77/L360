import { useEffect, useState } from "react";
import { Card, StatusBadge } from "../ui/ui";
import { ApiError, listRooms, type Room } from "../api/client";

// Read-only room directory. Admin create/edit lands in a later phase.
export function Rooms() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRooms()
      .then(setRooms)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't load rooms."))
      .finally(() => setLoading(false));
  }, []);

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
        <div style={{ overflowX: "auto" }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Room</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((r) => (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td>
                    <StatusBadge
                      variant={r.active ? "success" : "pending"}
                      label={r.active ? "Active" : "Inactive"}
                    />
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
