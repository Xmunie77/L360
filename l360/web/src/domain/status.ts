// Booking status -> badge mapping shared by the Calendar and Bookings screens.
// Per BOOKING_PAYMENT_SPEC.md §2: colour is never the only signal, and a
// missed session ("no_show") is always `pending`, never `danger`.

import type { BookingStatus } from "../api/client";
import type { StatusVariant } from "../ui/ui";

export const STATUS_LABEL: Record<BookingStatus, string> = {
  confirmed: "Confirmed",
  completed: "Completed",
  cancelled: "Cancelled",
  cancelled_late: "Cancelled (late)",
  no_show: "Missed",
};

export const STATUS_VARIANT: Record<BookingStatus, StatusVariant> = {
  confirmed: "success",
  completed: "success",
  cancelled: "pending",
  cancelled_late: "pending",
  no_show: "pending",
};

export function statusBadgeProps(status: BookingStatus): { variant: StatusVariant; label: string } {
  return { variant: STATUS_VARIANT[status], label: STATUS_LABEL[status] };
}
