import { useState } from "react";
import { Button, Card } from "../ui/ui";
import {
  ApiError,
  invoiceNow,
  setBookingStatus,
  type Booking,
  type BookingStatus,
} from "../api/client";
import { formatBookingWhen } from "../domain/datetime";

// The Confirm-session flow (Simon's design, 03/09/2026): tapping Confirm
// opens a MODAL — on a phone it reads like its own page — with the session's
// details on top and one big-button question per step:
//   Did this session take place? → Delivered / No show / Cancelled
//   Delivered → Send the invoice now? → Send invoice / Not now
//   No show / Cancelled → Charge? → Charge (→ invoice step)
//                                  / No charge → Why? (Child ill, …) → commit
// A cancelled_late booking opens straight at the charge question — its
// outcome is already known. Choices accumulate client-side and commit in
// ONE call chain at the final tap — Back and × never leave half-written
// state. The parent receives a live preview so the row's pills can morph.

export type OutcomePreview = { status: BookingStatus; charge_waived: boolean } | null;

type Step = "took_place" | "charge" | "reason" | "invoice";
type Outcome = "completed" | "no_show" | "cancelled_late";

export const WAIVE_REASONS = ["Child ill", "Educator ill", "Family emergency", "Other"] as const;

interface Props {
  booking: Booking;
  onPreview: (p: OutcomePreview) => void;
  onDone: () => void;
  onError: (msg: string) => void;
}

const OUTCOME_ECHO: Record<Outcome, string> = {
  completed: "Delivered ✓",
  no_show: "No show",
  cancelled_late: "Cancelled",
};

export function ConfirmSessionFlow({ booking, onPreview, onDone, onError }: Props) {
  // A late-cancelled session skips "did it take place" — only the charge
  // decision is open.
  const entryStep: Step = booking.status === "cancelled_late" ? "charge" : "took_place";
  const entryOutcome: Outcome = booking.status === "cancelled_late" ? "cancelled_late" : "completed";

  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>(entryStep);
  const [outcome, setOutcome] = useState<Outcome>(entryOutcome);
  const [busy, setBusy] = useState(false);

  const price =
    booking.client_price_cents !== null ? ` — €${(booking.client_price_cents / 100).toFixed(2)}` : "";

  function close() {
    setOpen(false);
    setStep(entryStep);
    setOutcome(entryOutcome);
    onPreview(null);
  }

  function choose(next: Outcome) {
    setOutcome(next);
    onPreview({ status: next, charge_waived: false });
    setStep(next === "completed" ? "invoice" : "charge");
  }

  async function commit(opts: { charge: boolean; sendInvoice: boolean; reason?: string }) {
    setBusy(true);
    try {
      await setBookingStatus(booking.id, outcome, opts.charge, opts.reason);
      if (opts.sendInvoice) {
        await invoiceNow(booking.id);
      }
      close();
      onDone();
    } catch (err) {
      close();
      onError(err instanceof ApiError ? err.detail : "Couldn't save the change.");
      onDone(); // refresh — the status commit may have landed even if the invoice failed
    } finally {
      setBusy(false);
    }
  }

  const trigger = (
    <Button type="button" variant="secondary" onClick={() => setOpen(true)}>
      {booking.status === "confirmed" ? "Confirm" : "Amend"}
    </Button>
  );

  if (!open) return trigger;


  return (
    <>
      {trigger}
      <div className="l360-modal-backdrop" onClick={close}>
        <div className="l360-modal-card" onClick={(e) => e.stopPropagation()}>
          <Card eyebrow="Confirm session" title={booking.client_label}>
            <p className="l360-field-hint" style={{ marginTop: 0, marginBottom: 4 }}>
              {formatBookingWhen(booking.start_utc)} · {booking.duration_minutes} min · {booking.room_name}
            </p>
            <p className="l360-field-hint" style={{ marginTop: 0, marginBottom: 16 }}>
              {booking.service_type_name ?? "Session"}
              {price} · {booking.educator_name}
              {(step !== "took_place" || entryStep === "charge") && <> · {OUTCOME_ECHO[outcome]}</>}
            </p>

            {step === "took_place" && (
              <>
                <p style={{ marginBottom: 12 }}>Did this session take place?</p>
                <Button type="button" variant="secondary" block style={{ marginBottom: 8 }} disabled={busy} onClick={() => choose("completed")}>
                  Delivered
                </Button>
                <Button type="button" variant="secondary" block style={{ marginBottom: 8 }} disabled={busy} onClick={() => choose("no_show")}>
                  No show
                </Button>
                <Button type="button" variant="secondary" block style={{ marginBottom: 8 }} disabled={busy} onClick={() => choose("cancelled_late")}>
                  Cancelled
                </Button>
              </>
            )}

            {step === "charge" && (
              <>
                <p style={{ marginBottom: 12 }}>Charge for this session?</p>
                <Button type="button" variant="secondary" block style={{ marginBottom: 8 }} disabled={busy} onClick={() => setStep("invoice")}>
                  Charge
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  block style={{ marginBottom: 8 }}
                  disabled={busy}
                  onClick={() => {
                    onPreview({ status: outcome, charge_waived: true });
                    setStep("reason");
                  }}
                >
                  No charge (fee waived)
                </Button>
                {entryStep === "took_place" && (
                  <Button type="button" variant="secondary" block style={{ marginBottom: 8 }} disabled={busy} onClick={() => { onPreview(null); setStep("took_place"); }}>
                    Back
                  </Button>
                )}
              </>
            )}

            {step === "reason" && (
              <>
                <p style={{ marginBottom: 12 }}>Why is the fee waived?</p>
                {WAIVE_REASONS.map((reason) => (
                  <Button
                    key={reason}
                    type="button"
                    variant="secondary"
                    block style={{ marginBottom: 8 }}
                    loading={busy}
                    loadingLabel="Saving…"
                    onClick={() => void commit({ charge: false, sendInvoice: false, reason })}
                  >
                    {reason}
                  </Button>
                ))}
                <Button type="button" variant="secondary" block style={{ marginBottom: 8 }} disabled={busy} onClick={() => setStep("charge")}>
                  Back
                </Button>
              </>
            )}

            {step === "invoice" && (
              <>
                <p style={{ marginBottom: 12 }}>Send the invoice now?</p>
                <Button
                  type="button"
                  variant="secondary"
                  block style={{ marginBottom: 8 }}
                  loading={busy}
                  loadingLabel="Sending…"
                  onClick={() => void commit({ charge: true, sendInvoice: true })}
                >
                  Send invoice{price}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  block style={{ marginBottom: 8 }}
                  disabled={busy}
                  onClick={() => void commit({ charge: true, sendInvoice: false })}
                >
                  Not now — monthly run
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  block style={{ marginBottom: 8 }}
                  disabled={busy}
                  onClick={() => {
                    if (outcome === "completed") {
                      onPreview(null);
                      setStep("took_place");
                    } else {
                      setStep("charge");
                    }
                  }}
                >
                  Back
                </Button>
              </>
            )}

            <Button type="button" variant="secondary" onClick={close} disabled={busy}>
              Close
            </Button>
          </Card>
        </div>
      </div>
    </>
  );
}

// Admin escape hatch, same modal pattern: void a mistriggered issued
// invoice (number kept, family told to ignore it) so the session unlocks.
export function VoidInvoiceModal({
  booking,
  onDone,
  onError,
  voidAction,
}: {
  booking: Booking;
  onDone: () => void;
  onError: (msg: string) => void;
  voidAction: (invoiceId: number) => Promise<unknown>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleVoid() {
    if (!booking.invoice_id) return;
    setBusy(true);
    try {
      await voidAction(booking.invoice_id);
      setOpen(false);
      onDone();
    } catch (err) {
      setOpen(false);
      onError(err instanceof ApiError ? err.detail : "Couldn't void the invoice.");
    } finally {
      setBusy(false);
    }
  }

  const trigger = (
    <Button type="button" variant="secondary" onClick={() => setOpen(true)}>
      Void / amend
    </Button>
  );
  if (!open) return trigger;

  return (
    <>
      {trigger}
      <div className="l360-modal-backdrop" onClick={() => setOpen(false)}>
        <div className="l360-modal-card" onClick={(e) => e.stopPropagation()}>
          <Card eyebrow="Void invoice" title={booking.invoice_number ?? "Invoice"}>
            <p style={{ marginBottom: 8 }}>
              This voids the invoice for {booking.client_label}'s session on{" "}
              {formatBookingWhen(booking.start_utc)}. The number is kept for the records and never
              reused; the session unlocks so it can be amended or re-invoiced.
            </p>
            <p className="l360-field-hint" style={{ marginTop: 0, marginBottom: 16 }}>
              Remember to tell the family to ignore the invoice they received.
            </p>
            <Button
              type="button"
              variant="destructive"
              style={{ width: "100%", marginBottom: 8 }}
              loading={busy}
              loadingLabel="Voiding…"
              onClick={() => void handleVoid()}
            >
              Void invoice
            </Button>
            <Button type="button" variant="secondary" onClick={() => setOpen(false)} disabled={busy}>
              Close
            </Button>
          </Card>
        </div>
      </div>
    </>
  );
}

// Cancelling inside the 24h window, as a modal (consistency, Simon
// 03/09/2026): charge or waive — and a waive asks why.
export function LateCancelModal({
  booking,
  cancelAction,
  onDone,
  onError,
}: {
  booking: Booking;
  cancelAction: (charge: boolean, reason?: string) => Promise<unknown>;
  onDone: () => void;
  onError: (msg: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [askReason, setAskReason] = useState(false);
  const [busy, setBusy] = useState(false);

  function close() {
    setOpen(false);
    setAskReason(false);
  }

  async function commit(charge: boolean, reason?: string) {
    setBusy(true);
    try {
      await cancelAction(charge, reason);
      close();
      onDone();
    } catch (err) {
      close();
      onError(err instanceof ApiError ? err.detail : "Couldn't cancel this booking.");
    } finally {
      setBusy(false);
    }
  }

  const trigger = (
    <Button type="button" variant="destructive" onClick={() => setOpen(true)}>
      Cancel
    </Button>
  );
  if (!open) return trigger;

  return (
    <>
      {trigger}
      <div className="l360-modal-backdrop" onClick={close}>
        <div className="l360-modal-card" onClick={(e) => e.stopPropagation()}>
          <Card eyebrow="Cancel session" title={booking.client_label}>
            <p className="l360-field-hint" style={{ marginTop: 0, marginBottom: 16 }}>
              {formatBookingWhen(booking.start_utc)} · {booking.duration_minutes} min ·{" "}
              {booking.room_name} · {booking.educator_name}
            </p>
            {!askReason ? (
              <>
                <p style={{ marginBottom: 12 }}>
                  This is a late cancellation (under 24 h) — charge for the session?
                </p>
                <Button
                  type="button"
                  variant="secondary"
                  block style={{ marginBottom: 8 }}
                  loading={busy}
                  loadingLabel="Cancelling…"
                  onClick={() => void commit(true)}
                >
                  Charge
                </Button>
                <Button type="button" variant="secondary" block style={{ marginBottom: 8 }} disabled={busy} onClick={() => setAskReason(true)}>
                  No charge (fee waived)
                </Button>
              </>
            ) : (
              <>
                <p style={{ marginBottom: 12 }}>Why is the fee waived?</p>
                {WAIVE_REASONS.map((reason) => (
                  <Button
                    key={reason}
                    type="button"
                    variant="secondary"
                    block style={{ marginBottom: 8 }}
                    loading={busy}
                    loadingLabel="Cancelling…"
                    onClick={() => void commit(false, reason)}
                  >
                    {reason}
                  </Button>
                ))}
                <Button type="button" variant="secondary" block style={{ marginBottom: 8 }} disabled={busy} onClick={() => setAskReason(false)}>
                  Back
                </Button>
              </>
            )}
            <Button type="button" variant="secondary" onClick={close} disabled={busy}>
              Close
            </Button>
          </Card>
        </div>
      </div>
    </>
  );
}
