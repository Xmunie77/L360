import { useEffect, useState } from "react";
import { Button, Card, StatusBadge } from "../ui/ui";
import { ApiError, cancelBooking, listBookings, type Booking } from "../api/client";
import { statusBadgeProps } from "../domain/status";
import { dayBoundsISO, formatBookingWhen, todayStr } from "../domain/datetime";

const LOOKAHEAD_DAYS = 14;

// Upcoming-bookings list — the "I just want a list, not a grid" view, and
// what stays usable on a phone. Same data as Calendar, table-shaped.
export function Bookings() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const { startISO } = dayBoundsISO(todayStr());
      const end = new Date(startISO);
      end.setDate(end.getDate() + LOOKAHEAD_DAYS);
      const rows = await listBookings({ start: startISO, end: end.toISOString() });
      setBookings(rows);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load bookings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCancel(id: number) {
    setCancellingId(id);
    setError(null);
    try {
      await cancelBooking(id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't cancel this booking.");
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <Card eyebrow="Scheduling" title="Bookings">
      <p style={{ marginBottom: 16 }}>
        Every session booked into a room over the next {LOOKAHEAD_DAYS} days, with client,
        educator and status at a glance.
      </p>

      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}

      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : bookings.length === 0 ? (
        <p className="l360-empty">No bookings in the next {LOOKAHEAD_DAYS} days.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Room</th>
                <th>Educator</th>
                <th>Learner</th>
                <th>Duration</th>
                <th>Status</th>
                <th>
                  <span className="l360-visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((b) => {
                const { variant, label } = statusBadgeProps(b.status);
                return (
                  <tr key={b.id}>
                    <td>{formatBookingWhen(b.start_utc)}</td>
                    <td>{b.room_name}</td>
                    <td>{b.educator_name}</td>
                    <td>{b.client_label}</td>
                    <td>{b.duration_minutes} min</td>
                    <td><StatusBadge variant={variant} label={label} /></td>
                    <td>
                      {b.status === "confirmed" && (
                        <Button
                          type="button"
                          variant="destructive"
                          onClick={() => handleCancel(b.id)}
                          loading={cancellingId === b.id}
                          loadingLabel="Cancelling…"
                        >
                          Cancel
                        </Button>
                      )}
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
