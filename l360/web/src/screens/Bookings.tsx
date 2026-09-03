import { useEffect, useState } from "react";
import { Button, Card, StatusBadge } from "../ui/ui";
import {
  ApiError,
  cancelBooking,
  listBookings,
  setBookingStatus,
  type Booking,
  type Me,
} from "../api/client";
import { statusBadgeProps } from "../domain/status";
import { dayBoundsISO, formatBookingWhen, todayStr } from "../domain/datetime";

const WINDOW_DAYS = 14;

// The charge question, asked inline in a row's action cell before a money
// decision is written: marking a no-show, or cancelling inside 24h.
type PendingAsk = { id: number; kind: "no_show" | "late_cancel" } | null;

// Bookings list — the last 14 days and the next 14. The recent past is the
// working half since 03/09/2026: sessions deliver (and bill) by default
// once their time passes, and this list is where the educator records the
// EXCEPTIONS — no-shows, and charge-or-waive decisions — until invoiced.
export function Bookings({ me }: { me: Me | null }) {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [pendingAsk, setPendingAsk] = useState<PendingAsk>(null);

  const isAdmin = me?.role === "admin";

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const { startISO } = dayBoundsISO(todayStr());
      const start = new Date(startISO);
      start.setDate(start.getDate() - WINDOW_DAYS);
      const end = new Date(startISO);
      end.setDate(end.getDate() + WINDOW_DAYS);
      const rows = await listBookings({
        start: start.toISOString(),
        end: end.toISOString(),
        // Educators see only their own sessions here; admins see everyone.
        mine: isAdmin ? undefined : true,
      });
      setBookings(rows);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load bookings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [isAdmin]);

  async function run(id: number, action: () => Promise<unknown>, failMsg: string) {
    setBusyId(id);
    setError(null);
    try {
      await action();
      setPendingAsk(null);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : failMsg);
    } finally {
      setBusyId(null);
    }
  }

  function handleCancelClick(b: Booking) {
    const hoursAway = (new Date(b.start_utc).getTime() - Date.now()) / 3_600_000;
    if (hoursAway < 24) {
      // Late cancellation — the canceller decides whether the family pays.
      setPendingAsk({ id: b.id, kind: "late_cancel" });
    } else {
      void run(b.id, () => cancelBooking(b.id), "Couldn't cancel this booking.");
    }
  }

  function canAmend(b: Booking): boolean {
    if (!me || b.invoiced) return false;
    return isAdmin || b.educator_id === me.id;
  }

  function rowActions(b: Booking) {
    const busy = busyId === b.id;
    const isPast = new Date(b.start_utc).getTime() <= Date.now();

    if (pendingAsk?.id === b.id) {
      const isNoShow = pendingAsk.kind === "no_show";
      const commit = (charge: boolean) =>
        void run(
          b.id,
          () => (isNoShow ? setBookingStatus(b.id, "no_show", charge) : cancelBooking(b.id, charge)),
          "Couldn't save the change.",
        );
      return (
        <span style={{ display: "inline-flex", gap: 6, alignItems: "center", whiteSpace: "nowrap" }}>
          <span className="l360-field-hint">{isNoShow ? "No show — charge?" : "Late cancel — charge?"}</span>
          <Button type="button" variant="secondary" onClick={() => commit(true)} loading={busy} loadingLabel="Saving…">
            Charge
          </Button>
          <Button type="button" variant="secondary" onClick={() => commit(false)} disabled={busy}>
            No charge
          </Button>
          <Button type="button" variant="secondary" onClick={() => setPendingAsk(null)} disabled={busy}>
            Back
          </Button>
        </span>
      );
    }

    if (b.status === "confirmed" && !isPast) {
      return (
        <Button
          type="button"
          variant="destructive"
          onClick={() => handleCancelClick(b)}
          loading={busy}
          loadingLabel="Cancelling…"
        >
          Cancel
        </Button>
      );
    }

    if (!canAmend(b)) return null;

    if ((b.status === "confirmed" || b.status === "completed") && isPast) {
      return (
        <Button type="button" variant="secondary" onClick={() => setPendingAsk({ id: b.id, kind: "no_show" })} disabled={busy}>
          No show
        </Button>
      );
    }
    if (b.status === "no_show") {
      return (
        <Button
          type="button"
          variant="secondary"
          onClick={() => void run(b.id, () => setBookingStatus(b.id, "completed", true), "Couldn't undo.")}
          loading={busy}
          loadingLabel="Saving…"
        >
          Undo
        </Button>
      );
    }
    if (b.status === "cancelled_late") {
      const nextCharge = b.charge_waived;
      return (
        <Button
          type="button"
          variant="secondary"
          onClick={() => void run(b.id, () => setBookingStatus(b.id, "completed", nextCharge), "Couldn't save the change.")}
          loading={busy}
          loadingLabel="Saving…"
        >
          {b.charge_waived ? "Charge" : "Waive charge"}
        </Button>
      );
    }
    return null;
  }

  return (
    <Card eyebrow="Scheduling" title="Bookings">
      <p style={{ marginBottom: 4 }}>
        {isAdmin ? "Every session" : "Your sessions"} from the last {WINDOW_DAYS} days to the next{" "}
        {WINDOW_DAYS}, with status at a glance.
      </p>
      <p className="l360-field-hint" style={{ marginTop: 0, marginBottom: 16 }}>
        Past sessions are billed automatically — only record the exceptions: mark a no show, and
        choose whether it's charged. (B) = the family is charged. Locked once invoiced.
      </p>

      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}

      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : bookings.length === 0 ? (
        <p className="l360-empty">No bookings in this window.</p>
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
                const { variant, label } = statusBadgeProps(b);
                return (
                  <tr key={b.id}>
                    <td>{formatBookingWhen(b.start_utc)}</td>
                    <td>{b.room_name}</td>
                    <td>{b.educator_name}</td>
                    <td>{b.client_label}</td>
                    <td>{b.duration_minutes} min</td>
                    <td><StatusBadge variant={variant} label={label} /></td>
                    <td>{rowActions(b)}</td>
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
