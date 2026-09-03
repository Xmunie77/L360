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
//   Did this session take place? → Delivered / No show / Session cancelled
//   Delivered → Send the invoice now? → Send invoice / Not now
//   No show / Session cancelled → Charge? → Charge (→ invoice step) / No charge
// Choices accumulate client-side and commit in ONE call chain at the final
// tap — Back and × never leave half-written state. The parent receives a
// live preview so the row's pills can morph while the modal is open.

export type OutcomePreview = { status: BookingStatus; charge_waived: boolean } | null;

type Step = "took_place" | "charge" | "invoice";
type Outcome = "completed" | "no_show" | "cancelled_late";

interface Props {
  booking: Booking;
  onPreview: (p: OutcomePreview) => void;
  onDone: () => void;
  onError: (msg: string) => void;
}

const OUTCOME_ECHO: Record<Outcome, string> = {
  completed: "Delivered ✓",
  no_show: "No show",
  cancelled_late: "Session cancelled",
};

export function ConfirmSessionFlow({ booking, onPreview, onDone, onError }: Props) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("took_place");
  const [outcome, setOutcome] = useState<Outcome>("completed");
  const [busy, setBusy] = useState(false);

  const price =
    booking.client_price_cents !== null ? ` — €${(booking.client_price_cents / 100).toFixed(2)}` : "";

  function close() {
    setOpen(false);
    setStep("took_place");
    setOutcome("completed");
    onPreview(null);
  }

  function choose(next: Outcome) {
    setOutcome(next);
    onPreview({ status: next, charge_waived: false });
    setStep(next === "completed" ? "invoice" : "charge");
  }

  async function commit(opts: { charge: boolean; sendInvoice: boolean }) {
    setBusy(true);
    try {
      await setBookingStatus(booking.id, outcome, opts.charge);
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

  const fullWidth = { width: "100%", marginBottom: 8 } as const;

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
              {step !== "took_place" && <> · {OUTCOME_ECHO[outcome]}</>}
            </p>

            {step === "took_place" && (
              <>
                <p style={{ marginBottom: 12 }}>Did this session take place?</p>
                <Button type="button" variant="secondary" style={fullWidth} disabled={busy} onClick={() => choose("completed")}>
                  Delivered
                </Button>
                <Button type="button" variant="secondary" style={fullWidth} disabled={busy} onClick={() => choose("no_show")}>
                  No show
                </Button>
                <Button type="button" variant="secondary" style={fullWidth} disabled={busy} onClick={() => choose("cancelled_late")}>
                  Session cancelled
                </Button>
              </>
            )}

            {step === "charge" && (
              <>
                <p style={{ marginBottom: 12 }}>Charge for this session?</p>
                <Button type="button" variant="secondary" style={fullWidth} disabled={busy} onClick={() => setStep("invoice")}>
                  Charge
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  style={fullWidth}
                  loading={busy}
                  loadingLabel="Saving…"
                  onClick={() => {
                    onPreview({ status: outcome, charge_waived: true });
                    void commit({ charge: false, sendInvoice: false });
                  }}
                >
                  No charge (fee waived)
                </Button>
                <Button type="button" variant="secondary" style={fullWidth} disabled={busy} onClick={() => { onPreview(null); setStep("took_place"); }}>
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
                  style={fullWidth}
                  loading={busy}
                  loadingLabel="Sending…"
                  onClick={() => void commit({ charge: true, sendInvoice: true })}
                >
                  Send invoice{price}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  style={fullWidth}
                  disabled={busy}
                  onClick={() => void commit({ charge: true, sendInvoice: false })}
                >
                  Not now — monthly run
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  style={fullWidth}
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
