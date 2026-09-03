// Booking status -> badge mapping shared by the Calendar and Bookings screens.
// Colour is never the only signal, and a missed session is `pending`, never
// `danger` (BOOKING_PAYMENT_SPEC.md §2).
//
// Since 03/09/2026 (Fran's delivered-by-default rule) the badge tells the
// human story, not the DB column: a future booking is "Booked", a past one
// is assumed "Delivered" and bills automatically, and "(B)" marks an
// exception the family is still charged for. Ladder: Booked → Delivered →
// Billed.

import type { BookingStatus } from "../api/client";
import type { StatusVariant } from "../ui/ui";

export interface BookingBadgeInput {
  status: BookingStatus;
  start_utc: string;
  invoiced: boolean;
  charge_waived: boolean;
}

export function statusBadgeProps(b: BookingBadgeInput): { variant: StatusVariant; label: string } {
  switch (b.status) {
    case "confirmed":
    case "completed": {
      if (b.invoiced) return { variant: "success", label: "Billed" };
      const isPast = new Date(b.start_utc).getTime() <= Date.now();
      return isPast ? { variant: "info", label: "Delivered" } : { variant: "success", label: "Booked" };
    }
    case "no_show":
      return { variant: "pending", label: b.charge_waived ? "No Show" : "No Show (B)" };
    case "cancelled_late":
      return { variant: "pending", label: b.charge_waived ? "Late cancel" : "Late cancel (B)" };
    case "cancelled":
      return { variant: "pending", label: "Cancelled" };
  }
}
