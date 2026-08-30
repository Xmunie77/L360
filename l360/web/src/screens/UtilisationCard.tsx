import { useEffect, useState } from "react";
import { Card, Input } from "../ui/ui";
import { ApiError, getUtilisationReport, type RoomUtilisation } from "../api/client";
import { todayStr } from "../domain/datetime";

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return err.status === 403 ? "Admins only — you don't have access to this section." : err.detail;
  }
  return fallback;
}

function firstOfMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

// Room-utilisation report. Lived on Statements until 30/08/2026; now an
// Admin sub-tab (it's an ops report, not a finance document — Simon).
export function UtilisationCard() {
  const [periodStart, setPeriodStart] = useState(firstOfMonth());
  const [periodEnd, setPeriodEnd] = useState(todayStr());
  const [rows, setRows] = useState<RoomUtilisation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getUtilisationReport(periodStart, periodEnd)
      .then(setRows)
      .catch((err) => setError(errorMessage(err, "Couldn't load the utilisation report.")))
      .finally(() => setLoading(false));
  }, [periodStart, periodEnd]);

  return (
    <Card eyebrow="Reports" title="Room utilisation">
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        <Input id="util-start" label="Period start" type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
        <Input id="util-end" label="Period end" type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
      </div>
      {error && <p className="l360-alert l360-alert-danger">{error}</p>}
      {loading && <p className="l360-empty">Loading…</p>}
      {!loading && (
        <div style={{ overflowX: "auto" }}>
          <table className="l360-table">
            <thead><tr><th>Room</th><th>Sessions</th><th>Booked time</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.room_id}>
                  <td>{r.room_name}</td>
                  <td>{r.session_count}</td>
                  <td>{Math.round((r.booked_minutes / 60) * 10) / 10} h</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
