import { useEffect, useState } from "react";
import { Button, Card, StatusBadge } from "../ui/ui";
import {
  ApiError,
  cancelBooking,
  listBookings,
  voidInvoice,
  type Booking,
  type Me,
} from "../api/client";
import { ConfirmSessionFlow, LateCancelModal, VoidInvoiceModal, type OutcomePreview } from "../components/ConfirmSessionFlow";
import { billingBadgeProps, statusBadgeProps } from "../domain/status";
import { dayBoundsISO, formatBookingWhenShort, todayStr } from "../domain/datetime";
import { MOBILE_QUERY, useMediaQuery } from "../hooks/useMediaQuery";

const WINDOW_DAYS = 14;

// "Room 1" -> "1": the column header already says Room, so the number
// alone keeps the column narrow (Simon, 04/09/2026).
function roomShort(name: string): string {
  const m = /^room\s+(.+)$/i.exec(name.trim());
  return m ? m[1] : name;
}

// Bookings list — the last 14 days and the next 14. The recent past is the
// working half: sessions deliver (and bill) by default once their time
// passes; the Confirm flow records what actually happened — and can send
// the invoice on the spot. Monthly billing runs remain the safety net.
export function Bookings({ me }: { me: Me | null }) {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
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
      setError(err instanceof ApiError ? err.detail : "Couldn't load sessions.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [isAdmin]);

  // Cancelling is irreversible and the button sits next to Confirm, so it
  // asks first — the same two-step the Calendar's detail modal uses
  // (a mis-tap here used to cancel a family's session outright).
  const [confirmingCancelId, setConfirmingCancelId] = useState<number | null>(null);
  const isMobile = useMediaQuery(MOBILE_QUERY);

  function setPreview(id: number, p: OutcomePreview) {
    setPreviews((prev) => ({ ...prev, [id]: p }));
  }

  async function run(id: number, action: () => Promise<unknown>, failMsg: string) {
    setBusyId(id);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : failMsg);
    } finally {
      setBusyId(null);
    }
  }

  function rowActions(b: Booking) {
    const busy = busyId === b.id;
    const isPast = new Date(b.start_utc).getTime() <= Date.now();

    if (b.status === "confirmed" && !isPast) {
      if (b.invoiced) return null; // on an issued invoice = locked
      const hoursAway = (new Date(b.start_utc).getTime() - Date.now()) / 3_600_000;
      if (hoursAway < 24) {
        // Late cancellation — modal asks charge / waive (+ reason).
        return (
          <LateCancelModal
            booking={b}
            cancelAction={(charge, reason) => cancelBooking(b.id, charge, reason)}
            onDone={() => void refresh()}
            onError={(msg) => setError(msg)}
          />
        );
      }
      if (confirmingCancelId === b.id) {
        return (
          <span style={{ display: "inline-flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <span>Cancel this session?</span>
            <Button
              type="button"
              variant="destructive"
              onClick={() =>
                void run(b.id, () => cancelBooking(b.id), "Couldn't cancel this booking.").then(() =>
                  setConfirmingCancelId(null),
                )
              }
              loading={busy}
              loadingLabel="Cancelling…"
            >
              Yes, cancel
            </Button>
            <Button type="button" variant="secondary" disabled={busy} onClick={() => setConfirmingCancelId(null)}>
              Keep it
            </Button>
          </span>
        );
      }
      return (
        <Button type="button" variant="destructive" onClick={() => setConfirmingCancelId(b.id)}>
          Cancel
        </Button>
      );
    }

    if (!me || (!isAdmin && b.educator_id !== me.id)) return null;

    // Invoiced = locked for educators; admins get the escape hatch — void
    // the mistriggered invoice, which unlocks the session (Simon, 03/09).
    if (b.invoiced) {
      if (!isAdmin || !b.invoice_id) return null;
      return (
        <VoidInvoiceModal
          booking={b}
          voidAction={(invId) => voidInvoice(invId)}
          onDone={() => void refresh()}
          onError={(msg) => setError(msg)}
        />
      );
    }

    // A waived fee is final for EDUCATORS; admins may revisit it.
    if (b.charge_waived && !isAdmin) return null;

    if ((b.status === "confirmed" || b.status === "completed" || b.status === "no_show" || b.status === "cancelled_late") && isPast) {
      return (
        <ConfirmSessionFlow
          booking={b}
          onPreview={(p) => setPreview(b.id, p)}
          onDone={() => void refresh()}
          onError={(msg) => setError(msg)}
        />
      );
    }
    // A future cancelled_late (cancelled inside 24h, session date not yet
    // reached): the charge decision is amendable through the same modal.
    if (b.status === "cancelled_late") {
      return (
        <ConfirmSessionFlow
          booking={b}
          onPreview={(p) => setPreview(b.id, p)}
          onDone={() => void refresh()}
          onError={(msg) => setError(msg)}
        />
      );
    }
    return null;
  }

  return (
    <Card>
      <p className="l360-field-hint" style={{ marginTop: 0, marginBottom: 16 }}>
        {isAdmin ? "Every session" : "Your sessions"}, ±{WINDOW_DAYS} days. Past sessions bill
        automatically — Confirm records exceptions and can send the invoice on the spot.
      </p>

      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}

      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : bookings.length === 0 ? (
        <p className="l360-empty">No sessions in this window.</p>
      ) : isMobile ? (
        /* The 8-column table is ~870px of nowrap content — on a phone the
           Confirm button needed a 500px sideways scroll to reach. Cards
           put the action in thumb range (04/09/2026 UI audit). */
        <div>
          {bookings.map((b) => {
            const preview = previews[b.id];
            const { variant, label } = statusBadgeProps(preview ? { ...b, ...preview } : b);
            const billing = billingBadgeProps(
              preview ? (preview.charge_waived ? "fee_waived" : "to_bill") : b.billing_state,
            );
            return (
              <div key={b.id} className="l360-session-card">
                <div className="l360-session-card-top">
                  <span style={{ fontWeight: 600 }}>{formatBookingWhenShort(b.start_utc)}</span>
                  <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
                    <StatusBadge variant={variant} label={preview ? `${label} …` : label} />
                    {billing && <StatusBadge variant={billing.variant} label={billing.label} />}
                  </span>
                </div>
                <p style={{ margin: "4px 0 2px", fontWeight: 600 }}>{b.client_label}</p>
                <p className="l360-field-hint" style={{ margin: "0 0 8px" }}>
                  {b.educator_name} · {b.room_name} · {b.duration_minutes} min
                </p>
                {rowActions(b)}
              </div>
            );
          })}
        </div>
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
                    <td style={{ whiteSpace: "nowrap" }}>{formatBookingWhenShort(b.start_utc)}</td>
                    <td style={{ textAlign: "center" }}>{roomShort(b.room_name)}</td>
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
