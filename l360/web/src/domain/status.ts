// Booking badges shared by the Calendar and Bookings screens.
//
// Two-column design (Simon, 03/09/2026): the STATUS pill says what happened
// to the session, the BILLING pill says where the money stands — one chip
// never carries both facts again. Colour is never the only signal, and a
// missed session is `pending`, never `danger` (BOOKING_PAYMENT_SPEC.md §2).

import type { BillingState, BookingStatus } from "../api/client";
import type { StatusVariant } from "../ui/ui";

export interface BookingBadgeInput {
  status: BookingStatus;
  start_utc: string;
}

// Outcome pill: Booked / Delivered / No show / Session cancelled / Cancelled.
// No "Delivered?" question mark — the presence of the Confirm button is
// what marks an unconfirmed session.
export function statusBadgeProps(b: BookingBadgeInput): { variant: StatusVariant; label: string } {
  switch (b.status) {
    case "confirmed": {
      const isPast = new Date(b.start_utc).getTime() <= Date.now();
      return isPast ? { variant: "info", label: "Delivered" } : { variant: "success", label: "Booked" };
    }
    case "completed":
      return { variant: "info", label: "Delivered" };
    case "no_show":
      return { variant: "pending", label: "No show" };
    case "cancelled_late":
      return { variant: "pending", label: "Session cancelled" };
    case "cancelled":
      return { variant: "pending", label: "Cancelled" };
  }
}

// Billing pill; null = show a plain dash (nothing owed, nothing pending).
export function billingBadgeProps(state: BillingState): { variant: StatusVariant; label: string } | null {
  switch (state) {
    case "to_bill":
      return { variant: "info", label: "To bill" };
    case "fee_waived":
      return { variant: "pending", label: "Fee waived" };
    case "invoice_sent":
      return { variant: "success", label: "Invoice sent" };
    case "paid":
      return { variant: "success", label: "Paid" };
    case "none":
      return null;
  }
}
