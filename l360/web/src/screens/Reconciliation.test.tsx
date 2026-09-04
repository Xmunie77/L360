import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Reconciliation } from "./Reconciliation";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    listUnmatchedTxns: vi.fn(),
    listInvoices: vi.fn(),
    syncPayments: vi.fn(),
    manualMatchPayment: vi.fn(),
    recordPayment: vi.fn(),
  };
});

import { listInvoices, listUnmatchedTxns, manualMatchPayment } from "../api/client";

const mockListUnmatchedTxns = vi.mocked(listUnmatchedTxns);
const mockListInvoices = vi.mocked(listInvoices);
const mockManualMatchPayment = vi.mocked(manualMatchPayment);

const SAMPLE_TXN = {
  id: 1,
  external_id: "ext-1",
  txn_date: "2026-08-20T10:00:00Z",
  amount_cents: 18000,
  currency: "EUR",
  reference: "INV-42",
  counterparty: "J. Borg",
  payment_id: null,
};

const SAMPLE_INVOICE = {
  id: 42,
  client_id: 5,
  client_label: "Borg family",
  number: "INV-42",
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  status: "issued" as const,
  total_cents: 18000,
  outstanding_cents: 18000,
  issued_at: "2026-08-15T00:00:00Z",
  due_date: "2026-09-01",
  notes: null,
  created_at: "2026-08-15T00:00:00Z",
};

describe("Reconciliation", () => {
  it("renders sync panel, unmatched transactions and record-payment form without crashing", async () => {
    mockListUnmatchedTxns.mockResolvedValue([SAMPLE_TXN]);
    mockListInvoices.mockImplementation(async (params) => (params?.status === "issued" ? [SAMPLE_INVOICE] : []));

    render(<Reconciliation />);

    expect(screen.getByRole("button", { name: "Sync payments" })).toBeTruthy();
    await waitFor(() => expect(screen.getByText(/J\. Borg/)).toBeTruthy());
    expect(screen.getByRole("button", { name: "Record payment" })).toBeTruthy();
  });

  it("matching an unmatched transaction to an invoice calls manualMatchPayment", async () => {
    mockListUnmatchedTxns.mockResolvedValue([SAMPLE_TXN]);
    mockListInvoices.mockImplementation(async (params) => (params?.status === "issued" ? [SAMPLE_INVOICE] : []));
    mockManualMatchPayment.mockResolvedValue({
      id: 1,
      invoice_id: 42,
      amount_cents: 18000,
      method: "bank_transfer",
      external_ref: null,
      received_at: "2026-08-20T10:00:00Z",
      match_status: "matched",
    });

    render(<Reconciliation />);

    await waitFor(() => expect(screen.getByText(/J\. Borg/)).toBeTruthy());

    const rowSelect = screen.getByLabelText("Match to invoice");
    fireEvent.change(rowSelect, { target: { value: "42" } });
    fireEvent.click(screen.getByRole("button", { name: "Match" }));

    await waitFor(() => expect(mockManualMatchPayment).toHaveBeenCalledWith(1, 42));
  });
});
