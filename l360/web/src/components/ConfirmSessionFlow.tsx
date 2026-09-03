import { useState } from "react";
import { Button } from "../ui/ui";
import { ApiError, invoiceNow, setBookingStatus, type Booking, type BookingStatus } from "../api/client";

// The Confirm-session stepper (Simon's "mix" design, 03/09/2026):
// the STATUS PILL stays a pure display; this component renders the
// Confirm/Amend button and walks the educator through the outcome.
// Choices accumulate client-side and commit in ONE go at the final step —
// Back never leaves half-written state. The parent receives a live
// preview of where the choices are heading so the pill can morph.

export type OutcomePreview = { status: BookingStatus; charge_waived: boolean } | null;

type Step = "idle" | "took_place" | "charge" | "invoice";

interface Props {
  booking: Booking;
  onPreview: (p: OutcomePreview) => void;
  onDone: () => void;
  onError: (msg: string) => void;
}

export function ConfirmSessionFlow({ booking, onPreview, onDone, onError }: Props) {
  const [step, setStep] = useState<Step>("idle");
  const [noShow, setNoShow] = useState(false);
  const [busy, setBusy] = useState(false);

  function reset() {
    setStep("idle");
    setNoShow(false);
    onPreview(null);
  }

  async function commit(opts: { status: "completed" | "no_show"; charge: boolean; sendInvoice: boolean }) {
    setBusy(true);
    try {
      await setBookingStatus(booking.id, opts.status, opts.charge);
      if (opts.sendInvoice) {
        await invoiceNow(booking.id);
      }
      reset();
      onDone();
    } catch (err) {
      reset();
      onError(err instanceof ApiError ? err.detail : "Couldn't save the change.");
      onDone(); // refresh — the status commit may have landed even if the invoice failed
    } finally {
      setBusy(false);
    }
  }

  if (step === "idle") {
    const label = booking.status === "confirmed" ? "Confirm" : "Amend";
    return (
      <Button
        type="button"
        variant="secondary"
        onClick={() => {
          setStep("took_place");
        }}
      >
        {label}
      </Button>
    );
  }

  const back = (
    <Button type="button" variant="secondary" onClick={reset} disabled={busy}>
      Back
    </Button>
  );

  if (step === "took_place") {
    return (
      <span className="l360-flow" style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <span className="l360-field-hint">Did this session take place?</span>
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          onClick={() => {
            setNoShow(false);
            onPreview({ status: "completed", charge_waived: false });
            setStep("invoice");
          }}
        >
          Yes
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          onClick={() => {
            setNoShow(true);
            onPreview({ status: "no_show", charge_waived: false });
            setStep("charge");
          }}
        >
          No show
        </Button>
        {back}
      </span>
    );
  }

  if (step === "charge") {
    return (
      <span className="l360-flow" style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <span className="l360-field-hint">Charge for this session?</span>
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          onClick={() => {
            onPreview({ status: "no_show", charge_waived: false });
            setStep("invoice");
          }}
        >
          Charge
        </Button>
        <Button
          type="button"
          variant="secondary"
          loading={busy}
          loadingLabel="Saving…"
          onClick={() => void commit({ status: "no_show", charge: false, sendInvoice: false })}
        >
          No charge
        </Button>
        {back}
      </span>
    );
  }

  // step === "invoice" — the final choice; commits happen here.
  const status = noShow ? ("no_show" as const) : ("completed" as const);
  return (
    <span className="l360-flow" style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
      <span className="l360-field-hint">Send the invoice now?</span>
      <Button
        type="button"
        variant="secondary"
        loading={busy}
        loadingLabel="Sending…"
        onClick={() => void commit({ status, charge: true, sendInvoice: true })}
      >
        Send invoice
      </Button>
      <Button
        type="button"
        variant="secondary"
        disabled={busy}
        onClick={() => void commit({ status, charge: true, sendInvoice: false })}
      >
        Later — monthly run
      </Button>
      {back}
    </span>
  );
}
