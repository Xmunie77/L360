import { describe, expect, it } from "vitest";
import { billingBadgeProps, statusBadgeProps } from "./status";

const past = new Date(Date.now() - 3_600_000).toISOString();
const future = new Date(Date.now() + 3_600_000).toISOString();

function outcome(status: string, start_utc: string = future) {
  return statusBadgeProps({ status: status as never, start_utc });
}

describe("statusBadgeProps — the outcome pill", () => {
  it("future confirmed reads Booked", () => {
    expect(outcome("confirmed")).toEqual({ variant: "success", label: "Booked" });
  });

  it("past confirmed and completed both read Delivered — the Confirm button marks unconfirmed, not the pill", () => {
    expect(outcome("confirmed", past)).toEqual({ variant: "info", label: "Delivered" });
    expect(outcome("completed", past)).toEqual({ variant: "info", label: "Delivered" });
  });

  it("the exception outcomes use Simon's vocabulary", () => {
    expect(outcome("no_show").label).toBe("No show");
    expect(outcome("cancelled_late").label).toBe("Cancelled");
    expect(outcome("cancelled").label).toBe("Cancelled");
  });
});

describe("billingBadgeProps — the money pill", () => {
  it("maps every state", () => {
    expect(billingBadgeProps("to_bill")).toEqual({ variant: "info", label: "To bill" });
    expect(billingBadgeProps("fee_waived")).toEqual({ variant: "pending", label: "Fee waived" });
    expect(billingBadgeProps("invoice_sent")).toEqual({ variant: "success", label: "Invoice sent" });
    expect(billingBadgeProps("paid")).toEqual({ variant: "success", label: "Paid" });
  });

  it("none renders no pill (dash in the table)", () => {
    expect(billingBadgeProps("none")).toBeNull();
  });
});
