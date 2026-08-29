import { useEffect, useState } from "react";
import { Card } from "../ui/ui";
import { ApiError, listClients, type Client } from "../api/client";

// Read-only client directory. The brief (non-admin) shape from /api/clients
// — no phone/notes exposed to non-admin staff. Admin create/edit lands in a
// later phase.
export function Clients() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listClients()
      .then(setClients)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't load learners."))
      .finally(() => setLoading(false));
  }, []);

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
        <div style={{ overflowX: "auto" }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Parent / Guardian</th>
                <th>Child's name</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.id}>
                  <td>{c.guardian_first_name} {c.guardian_surname}</td>
                  <td>{c.child_name ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
