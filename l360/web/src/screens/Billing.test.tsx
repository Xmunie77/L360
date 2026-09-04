import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Billing } from "./Billing";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    listInvoices: vi.fn(),
    runBilling: vi.fn(),
    getInvoice: vi.fn(),
    issueInvoice: vi.fn(),
  };
});

import { getInvoice, issueInvoice, listInvoices } from "../api/client";

const mockListInvoices = vi.mocked(listInvoices);
const mockGetInvoice = vi.mocked(getInvoice);
const mockIssueInvoice = vi.mocked(issueInvoice);

const SAMPLE_INVOICE = {
  id: 1,
  client_id: 5,
  client_label: "Aġius family",
  number: null,
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  status: "draft" as const,
  total_cents: 18000,
  outstanding_cents: 18000,
  issued_at: null,
  due_date: null,
  notes: null,
  created_at: "2026-08-28T00:00:00Z",
};

describe("Billing", () => {
  it("renders the run-billing panel and the invoice list without crashing", async () => {
    mockListInvoices.mockResolvedValue([SAMPLE_INVOICE]);

    render(<Billing />);

    expect(screen.getByRole("button", { name: "Run billing" })).toBeTruthy();
    await waitFor(() => expect(screen.getByText("Aġius family")).toBeTruthy());
  });

  it("issuing a draft invoice from the detail view calls issueInvoice", async () => {
    mockListInvoices.mockResolvedValue([SAMPLE_INVOICE]);
    mockGetInvoice.mockResolvedValue({
      ...SAMPLE_INVOICE,
      lines: [
        {
          id: 1,
          booking_id: 10,
          description: "Session with M. Vella",
          unit_price_cents: 18000,
          quantity: 1,
          amount_cents: 18000,
        },
      ],
    });
    mockIssueInvoice.mockResolvedValue({ ...SAMPLE_INVOICE, status: "issued", number: "INV-1" });

    render(<Billing />);

    await waitFor(() => expect(screen.getByText("Aġius family")).toBeTruthy());
    fireEvent.click(screen.getByText("Aġius family"));

    await waitFor(() => expect(screen.getByRole("button", { name: "Issue invoice" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Issue invoice" }));
    // Issuing numbers the invoice and emails the family, so it now asks
    // first, spelling out who gets the email.
    expect(mockIssueInvoice).not.toHaveBeenCalled();
    expect(screen.getByText(/emails it to/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Issue & email" }));

    await waitFor(() => expect(mockIssueInvoice).toHaveBeenCalledWith(1));
    // Success stays on screen instead of the modal silently vanishing.
    await waitFor(() => expect(screen.getByText(/issued and emailed to/)).toBeTruthy());
  });
});
