import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button, formatMoney, Money, StatusBadge } from "./ui";

describe("Button", () => {
  it("renders its label", () => {
    render(<Button>Pay €45</Button>);
    expect(screen.getByText("Pay €45")).toBeTruthy();
  });

  it("swaps to the loading label and marks aria-busy", () => {
    render(<Button loading loadingLabel="Paying…">Pay €45</Button>);
    const btn = screen.getByRole("button", { name: "Paying…" });
    expect(btn.getAttribute("aria-busy")).toBe("true");
  });
});

describe("StatusBadge", () => {
  it("always renders a text label, never colour alone", () => {
    render(<StatusBadge variant="pending" label="No-show" />);
    expect(screen.getByText("No-show")).toBeTruthy();
  });
});

describe("formatMoney", () => {
  it("formats integer cents as euros with two decimals", () => {
    expect(formatMoney(123456)).toBe("€1,234.56");
  });
});

describe("Money", () => {
  it("renders formatted cents in the mono class", () => {
    render(<Money cents={4500} />);
    const el = screen.getByText("€45.00");
    expect(el.className).toContain("l360-mono");
  });
});
