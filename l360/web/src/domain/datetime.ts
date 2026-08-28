// Small date/time helpers shared by the Calendar and Bookings screens.
// Bookings carry `start_utc` as an ISO datetime string; the grid displays
// everything in the viewer's local time (Malta staff run this in Malta time).

/** "YYYY-MM-DD" for the given Date, in local time. */
export function toDateInputValue(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function todayStr(): string {
  return toDateInputValue(new Date());
}

/** Local midnight..next-midnight for a "YYYY-MM-DD" day, as ISO strings suitable for /api/bookings start/end. */
export function dayBoundsISO(dateStr: string): { startISO: string; endISO: string } {
  const start = new Date(`${dateStr}T00:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { startISO: start.toISOString(), endISO: end.toISOString() };
}

/** 0=Monday .. 6=Sunday for a "YYYY-MM-DD" date, in local time (matches the API's `weekday`). */
export function mondayBasedWeekday(dateStr: string): number {
  return (new Date(`${dateStr}T00:00:00`).getDay() + 6) % 7;
}

/** Combine a "YYYY-MM-DD" date and "HH:MM" local time into an ISO datetime string. */
export function combineDateTime(dateStr: string, timeStr: string): string {
  return new Date(`${dateStr}T${timeStr}:00`).toISOString();
}

/** "HH:MM" for an ISO datetime, in local time. */
export function toTimeInputValue(iso: string): string {
  const d = new Date(iso);
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

/** Hour (with fraction) an ISO datetime falls at, in local time — e.g. 9:30 -> 9.5. */
export function localHourFraction(iso: string): number {
  const d = new Date(iso);
  return d.getHours() + d.getMinutes() / 60;
}

/** "09:00" style label for a whole/half hour. */
export function formatHourLabel(hour: number): string {
  const h = Math.floor(hour);
  const m = Math.round((hour - h) * 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

const DAY_LABEL_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatBookingWhen(iso: string): string {
  return DAY_LABEL_FORMATTER.format(new Date(iso));
}
