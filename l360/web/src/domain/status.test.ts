import { describe, expect, it } from "vitest";
import { statusBadgeProps } from "./status";

const past = new Date(Date.now() - 3_600_000).toISOString();
const future = new Date(Date.now() + 3_600_000).toISOString();

function badge(status: string, opts: Partial<{ start_utc: string; invoiced: boolean; charge_waived: boolean }> = {}) {
  return statusBadgeProps({
    status: status as never,
    start_utc: opts.start_utc ?? future,
    invoiced: opts.invoiced ?? false,
    charge_waived: opts.charge_waived ?? false,
  });
}

describe("statusBadgeProps — the Booked → Delivered → Billed ladder", () => {
  it("future confirmed reads Booked", () => {
    expect(badge("confirmed")).toEqual({ variant: "success", label: "Booked" });
  });

  it("past confirmed reads Delivered? — assumed, awaiting the Confirm flow", () => {
    expect(badge("confirmed", { start_utc: past })).toEqual({ variant: "info", label: "Delivered?" });
  });

  it("educator-confirmed (completed) reads Delivered, no question mark", () => {
    expect(badge("completed", { start_utc: past })).toEqual({ variant: "info", label: "Delivered" });
  });

  it("an invoiced session reads Billed", () => {
    expect(badge("confirmed", { start_utc: past, invoiced: true }).label).toBe("Billed");
    expect(badge("completed", { start_utc: past, invoiced: true }).label).toBe("Billed");
  });

  it("(B) marks a charged exception, (W) a waived one", () => {
    expect(badge("no_show").label).toBe("No Show (B)");
    expect(badge("no_show", { charge_waived: true }).label).toBe("No Show (W)");
    expect(badge("cancelled_late").label).toBe("Late cancel (B)");
    expect(badge("cancelled_late", { charge_waived: true }).label).toBe("Late cancel (W)");
  });

  it("an in-time cancellation is just Cancelled", () => {
    expect(badge("cancelled")).toEqual({ variant: "pending", label: "Cancelled" });
  });
});
