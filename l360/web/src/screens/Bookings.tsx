import { useEffect, useState } from "react";
import { Button, Card, StatusBadge } from "../ui/ui";
import {
  ApiError,
  cancelBooking,
  listBookings,
  setBookingStatus,
  voidInvoice,
  type Booking,
  type Me,
} from "../api/client";
import { ConfirmSessionFlow, type OutcomePreview } from "../components/ConfirmSessionFlow";
import { billingBadgeProps, statusBadgeProps } from "../domain/status";
import { dayBoundsISO, formatBookingWhen, todayStr } from "../domain/datetime";

const WINDOW_DAYS = 14;

// Bookings list — the last 14 days and the next 14. The recent past is the
// working half: sessions deliver (and bill) by default once their time
// passes; the Confirm flow records what actually happened — and can send
// the invoice on the spot. Monthly billing runs remain the safety net.
export function Bookings({ me }: { me: Me | null }) {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  // Late-cancellation charge question for the Cancel button.
  const [cancelAskId, setCancelAskId] = useState<number | null>(null);
  // Admin's void-invoice confirmation step.
  const [voidAskId, setVoidAskId] = useState<number | null>(null);
  // Live pill preview while a row's Confirm flow is mid-decision.
  const [previews, setPreviews] = useState<Record<number, OutcomePreview>>({});

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

  function setPreview(id: number, p: OutcomePreview) {
    setPreviews((prev) => ({ ...prev, [id]: p }));
  }

  async function run(id: number, action: () => Promise<unknown>, failMsg: string) {
    setBusyId(id);
    setError(null);
    try {
      await action();
      setCancelAskId(null);
      setVoidAskId(null);
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
      setCancelAskId(b.id);
    } else {
      void run(b.id, () => cancelBooking(b.id), "Couldn't cancel this booking.");
    }
  }

  function rowActions(b: Booking) {
    const busy = busyId === b.id;
    const isPast = new Date(b.start_utc).getTime() <= Date.now();

    if (cancelAskId === b.id) {
      return (
        <span style={{ display: "inline-flex", gap: 6, alignItems: "center", whiteSpace: "nowrap" }}>
          <span className="l360-field-hint">Late cancel — charge?</span>
          <Button type="button" variant="secondary" onClick={() => void run(b.id, () => cancelBooking(b.id, true), "Couldn't cancel.")} loading={busy} loadingLabel="Saving…">
            Charge
          </Button>
          <Button type="button" variant="secondary" onClick={() => void run(b.id, () => cancelBooking(b.id, false), "Couldn't cancel.")} disabled={busy}>
            No charge
          </Button>
          <Button type="button" variant="secondary" onClick={() => setCancelAskId(null)} disabled={busy}>
            Back
          </Button>
        </span>
      );
    }

    if (b.status === "confirmed" && !isPast) {
      if (b.invoiced) return null; // on an issued invoice = locked
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

    if (!me || (!isAdmin && b.educator_id !== me.id)) return null;

    // Invoiced = locked for educators; admins get the escape hatch — void
    // the mistriggered invoice (family is told to ignore it), which
    // unlocks the session for amendment (Simon, 03/09/2026).
    if (b.invoiced) {
      if (!isAdmin || !b.invoice_id) return null;
      if (voidAskId === b.id) {
        return (
          <span style={{ display: "inline-flex", gap: 6, alignItems: "center", whiteSpace: "nowrap" }}>
            <span className="l360-field-hint">Void {b.invoice_number ?? "invoice"}? Tell the family to ignore it.</span>
            <Button
              type="button"
              variant="destructive"
              onClick={() => void run(b.id, () => voidInvoice(b.invoice_id as number), "Couldn't void the invoice.")}
              loading={busy}
              loadingLabel="Voiding…"
            >
              Void invoice
            </Button>
            <Button type="button" variant="secondary" onClick={() => setVoidAskId(null)} disabled={busy}>
              Back
            </Button>
          </span>
        );
      }
      return (
        <Button type="button" variant="secondary" onClick={() => setVoidAskId(b.id)} disabled={busy}>
          Void / amend
        </Button>
      );
    }

    // A waived fee is final for EDUCATORS — no one-tap "Charge" undo
    // (Simon, 03/09/2026). Admins may revisit it.
    if (b.charge_waived && !isAdmin) return null;
    if (b.charge_waived && b.status === "cancelled_late") {
      return (
        <Button
          type="button"
          variant="secondary"
          onClick={() => void run(b.id, () => setBookingStatus(b.id, "cancelled_late", true), "Couldn't save the change.")}
          loading={busy}
          loadingLabel="Saving…"
        >
          Charge
        </Button>
      );
    }

    if ((b.status === "confirmed" || b.status === "completed" || b.status === "no_show") && isPast) {
      return (
        <ConfirmSessionFlow
          booking={b}
          onPreview={(p) => setPreview(b.id, p)}
          onDone={() => void refresh()}
          onError={(msg) => setError(msg)}
        />
      );
    }
    if (b.status === "cancelled_late") {
      return (
        <Button
          type="button"
          variant="secondary"
          onClick={() => void run(b.id, () => setBookingStatus(b.id, "cancelled_late", false), "Couldn't save the change.")}
          loading={busy}
          loadingLabel="Saving…"
        >
          Waive charge
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
        Past sessions are assumed delivered and bill automatically — Confirm records what actually
        happened and can send the invoice on the spot. Billing shows where the money stands; a
        session locks once its invoice is sent.
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
                <th>Billing</th>
                <th>
                  <span className="l360-visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((b) => {
                const preview = previews[b.id];
                const { variant, label } = statusBadgeProps(preview ? { ...b, ...preview } : b);
                // While the flow previews a choice, billing previews too:
                // waived → Fee waived, otherwise the outcome will bill.
                const billing = billingBadgeProps(
                  preview ? (preview.charge_waived ? "fee_waived" : "to_bill") : b.billing_state,
                );
                return (
                  <tr key={b.id}>
                    <td>{formatBookingWhen(b.start_utc)}</td>
                    <td>{b.room_name}</td>
                    <td>{b.educator_name}</td>
                    <td>{b.client_label}</td>
                    <td>{b.duration_minutes} min</td>
                    <td><StatusBadge variant={variant} label={preview ? `${label} …` : label} /></td>
                    <td>
                      {billing ? (
                        <StatusBadge variant={billing.variant} label={billing.label} />
                      ) : (
                        <span className="l360-field-hint">–</span>
                      )}
                    </td>
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
