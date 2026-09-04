import { describe, expect, it } from "vitest";
import { formatBookingWhenShort } from "./datetime";

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
