import { useEffect, useState } from "react";
import { Card, StatusBadge } from "../ui/ui";
import { ApiError, listEducators, type Educator } from "../api/client";

// Read-only educator directory. Admin create/edit/pay-rate lands in a later phase.
export function Educators() {
  const [educators, setEducators] = useState<Educator[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listEducators()
      .then(setEducators)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't load educators."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card eyebrow="Directory" title="Educators">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}

      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : educators.length === 0 ? (
        <p className="l360-empty">No educators configured yet.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {educators.map((e) => (
                <tr key={e.id}>
                  <td>{e.full_name}</td>
                  <td>{e.email}</td>
                  <td>
                    <StatusBadge
                      variant={e.active ? "success" : "pending"}
                      label={e.active ? "Active" : "Inactive"}
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
