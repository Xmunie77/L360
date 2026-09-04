import { describe, expect, it } from "vitest";
import { addDays, formatBookingWhenShort, localDateStr, startOfWeek, weekDates } from "./datetime";

describe("formatBookingWhenShort", () => {
  it("renders Malta day-first with a 2-digit year and no comma", () => {
    // Local time — the app runs on Malta machines; the test asserts the
    // shape (dd/mm/yy hh:mm), not a fixed hour across timezones.
    const iso = new Date(2026, 8, 4, 8, 0).toISOString(); // 04/09/2026 08:00 local
    expect(formatBookingWhenShort(iso)).toBe("04/09/26 08:00");
  });

  it("keeps 24-hour time in the afternoon", () => {
    const iso = new Date(2026, 11, 31, 17, 45).toISOString();
    expect(formatBookingWhenShort(iso)).toBe("31/12/26 17:45");
  });
});

describe("week helpers", () => {
  it("starts the week on Monday", () => {
    expect(startOfWeek("2026-09-04")).toBe("2026-08-31"); // a Friday -> its Monday
    expect(startOfWeek("2026-08-31")).toBe("2026-08-31"); // Monday is its own start
    expect(startOfWeek("2026-09-06")).toBe("2026-08-31"); // Sunday belongs to the week before
  });

  it("spans a month boundary", () => {
    expect(weekDates("2026-09-02")).toEqual([
      "2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03",
      "2026-09-04", "2026-09-05", "2026-09-06",
    ]);
  });

  it("keeps calendar days whole across the DST change", () => {
    // Malta clocks go back on 25/10/2026 — a naive +24h would repeat a day.
    expect(weekDates("2026-10-26")).toEqual([
      "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29",
      "2026-10-30", "2026-10-31", "2026-11-01",
    ]);
    expect(addDays("2026-10-24", 2)).toBe("2026-10-26");
  });

  it("buckets an instant into its LOCAL day", () => {
    const lateEvening = new Date(2026, 8, 4, 23, 30);
    expect(localDateStr(lateEvening.toISOString())).toBe("2026-09-04");
    const justAfterMidnight = new Date(2026, 8, 5, 0, 15);
    expect(localDateStr(justAfterMidnight.toISOString())).toBe("2026-09-05");
  });
});
