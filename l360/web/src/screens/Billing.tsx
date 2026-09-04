import { useEffect, useState, type FormEvent } from "react";
import { Modal } from "../components/Modal";
import { Button, Card, Input, Money, Select, StatusBadge, type StatusVariant } from "../ui/ui";
import {
  ApiError,
  getInvoice,
  issueInvoice,
  listInvoices,
  runBilling,
  type BillingRunResult,
  type Invoice,
  type InvoiceDetail,
  type InvoiceStatus,
} from "../api/client";
import { formatDateShort, todayStr } from "../domain/datetime";

const INVOICE_STATUS_LABEL: Record<InvoiceStatus, string> = {
  draft: "Draft",
  issued: "Issued",
  paid: "Paid",
  partially_paid: "Partially paid",
  void: "Void",
};

const INVOICE_STATUS_VARIANT: Record<InvoiceStatus, StatusVariant> = {
  draft: "pending",
  issued: "info",
  paid: "success",
  partially_paid: "info",
  void: "pending",
};

const STATUS_FILTER_OPTIONS = [
  { value: "", label: "All statuses" },
  ...(Object.keys(INVOICE_STATUS_LABEL) as InvoiceStatus[]).map((s) => ({
    value: s,
    label: INVOICE_STATUS_LABEL[s],
  })),
];

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return err.status === 403 ? "Admins only — you don't have access to this section." : err.detail;
  }
  return fallback;
}

// Monthly billing: run a billing cycle over a period, then list/issue the
// resulting invoices. Draft invoices are created by the run; issuing sends
// the client their invoice email and locks the numbering.
/** The Run-billing card on its own — Finance's first pill (Simon, 04/09/2026). */
export function RunBilling() {
  return <RunBillingPanel onRun={() => {}} />;
}

export function Billing({ showRun = true }: { showRun?: boolean } = {}) {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<number | null>(null);

  async function refreshInvoices() {
    setLoading(true);
    setLoadError(null);
    try {
      const rows = await listInvoices(statusFilter ? { status: statusFilter } : {});
      setInvoices(rows);
      setForbidden(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setForbidden(true);
      setLoadError(errorMessage(err, "Couldn't load invoices."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshInvoices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  if (forbidden) {
    return (
      <Card eyebrow="Finance" title="Billing">
        <p className="l360-empty">Admins only — you don't have access to this section.</p>
      </Card>
    );
  }

  return (
    <>
      {showRun && <RunBillingPanel onRun={refreshInvoices} />}

      <Card eyebrow="Finance" title="Invoices">
        <div style={{ marginBottom: 16, maxWidth: 260 }}>
          <Select
            id="invoice-status-filter"
            label="Filter by status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as InvoiceStatus | "")}
            options={STATUS_FILTER_OPTIONS}
          />
        </div>

        {loadError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {loadError}
          </div>
        )}

        {loading ? (
          <p className="l360-empty">Loading…</p>
        ) : invoices.length === 0 ? (
          <p className="l360-empty">No invoices for this filter yet.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="l360-table">
              <thead>
                <tr>
                  <th>Number</th>
                  <th>Learner</th>
                  <th>Period</th>
                  <th>Status</th>
                  <th>Total</th>
                  <th>Outstanding</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr
                    key={inv.id}
                    onClick={() => setSelectedInvoiceId(inv.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{inv.number ?? "draft"}</td>
                    <td>{inv.client_label}</td>
                    <td>
                      {formatDateShort(inv.period_start)} – {formatDateShort(inv.period_end)}
                    </td>
                    <td>
                      <StatusBadge
                        variant={INVOICE_STATUS_VARIANT[inv.status]}
                        label={INVOICE_STATUS_LABEL[inv.status]}
                      />
                    </td>
                    <td><Money cents={inv.total_cents} /></td>
                    <td><Money cents={inv.outstanding_cents} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {selectedInvoiceId !== null && (
        <InvoiceDetailModal
          invoiceId={selectedInvoiceId}
          onClose={() => setSelectedInvoiceId(null)}
          onChanged={() => {
            setSelectedInvoiceId(null);
            refreshInvoices();
          }}
        />
      )}
    </>
  );
}

// --- run billing panel -------------------------------------------------

function firstOfMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

function RunBillingPanel({ onRun }: { onRun: () => void }) {
  // First-of-month -> today, like every other Finance period control. The
  // old today->today default covered one day and drafted nothing.
  const [periodStart, setPeriodStart] = useState(firstOfMonth());
  const [periodEnd, setPeriodEnd] = useState(todayStr());
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BillingRunResult | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (periodEnd < periodStart) {
      setError("The period end is before its start.");
      return;
    }
    setError(null);
    setResult(null);
    setRunning(true);
    try {
      const res = await runBilling(periodStart, periodEnd);
      setResult(res);
      onRun();
    } catch (err) {
      setError(errorMessage(err, "Couldn't run billing for this period."));
    } finally {
      setRunning(false);
    }
  }

  return (
    <Card eyebrow="Finance" title="Run billing">
      <p style={{ marginBottom: 16 }}>
        The monthly safety net. Individual sessions can be invoiced on the spot from Sessions
        (Delivered? → Send invoice); this run sweeps up everything still unbilled in the period —
        delivered sessions plus charged no-shows and cancellations — into one draft invoice per
        client. Sessions already invoiced or with the fee waived are never picked up again, and
        clients with nothing billable are skipped, not invoiced for zero.
      </p>
      <form onSubmit={handleSubmit} noValidate>
        {error && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {error}
          </div>
        )}
        {result && (
          <div className="l360-alert l360-alert-info" role="status">
            <p style={{ margin: 0 }}>
              {result.created.length} invoice{result.created.length === 1 ? "" : "s"} drafted,{" "}
              {result.skipped_clients.length} client{result.skipped_clients.length === 1 ? "" : "s"} had
              nothing to bill.
              {result.created.length > 0 && " Review and issue them under Invoices."}
            </p>
            {result.created.length > 0 && (
              <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                {result.created.map((inv) => (
                  <li key={inv.id}>
                    {inv.client_label} — <Money cents={inv.total_cents} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
          <Input
            id="billing-period-start"
            label="Period start"
            type="date"
            required
            value={periodStart}
            onChange={(e) => setPeriodStart(e.target.value)}
          />
          <Input
            id="billing-period-end"
            label="Period end"
            type="date"
            required
            value={periodEnd}
            onChange={(e) => setPeriodEnd(e.target.value)}
          />
          <div style={{ marginBottom: 16 }}>
            <Button type="submit" loading={running} loadingLabel="Running…">
              Run billing
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}

// --- invoice detail modal ------------------------------------------------

interface InvoiceDetailModalProps {
  invoiceId: number;
  onClose: () => void;
  onChanged: () => void;
}

function InvoiceDetailModal({ invoiceId, onClose, onChanged }: InvoiceDetailModalProps) {
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [issuing, setIssuing] = useState(false);
  const [issueError, setIssueError] = useState<string | null>(null);
  const [confirmingIssue, setConfirmingIssue] = useState(false);
  const [issuedMessage, setIssuedMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getInvoice(invoiceId)
      .then((inv) => {
        if (!cancelled) setInvoice(inv);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(errorMessage(err, "Couldn't load this invoice."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [invoiceId]);

  async function handleIssue() {
    setIssueError(null);
    setIssuing(true);
    try {
      await issueInvoice(invoiceId);
      // Stay open and say what happened — issuing numbers the invoice AND
      // emails the family, and before 04/09/2026 the modal just vanished
      // with no confirmation either had occurred.
      const refreshed = await getInvoice(invoiceId);
      setInvoice(refreshed);
      setConfirmingIssue(false);
      setIssuedMessage(
        `Invoice ${refreshed.number ?? ""} issued and emailed to ${refreshed.client_label}.`,
      );
    } catch (err) {
      setIssueError(errorMessage(err, "Couldn't issue this invoice."));
    } finally {
      setIssuing(false);
    }
  }

  function close() {
    // The list behind needs refreshing once an issue has happened.
    if (issuedMessage) onChanged();
    else onClose();
  }

  return (
    <Modal onClose={close}>
        <Card eyebrow="Invoice" title={invoice?.number ?? "Draft invoice"}>
          {loading && <p className="l360-empty">Loading…</p>}
          {loadError && (
            <div className="l360-alert l360-alert-danger" role="alert">
              ⚠ {loadError}
            </div>
          )}

          {invoice && (
            <>
              <p style={{ marginBottom: 8 }}>{invoice.client_label}</p>
              <p style={{ marginBottom: 16, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <StatusBadge
                  variant={INVOICE_STATUS_VARIANT[invoice.status]}
                  label={INVOICE_STATUS_LABEL[invoice.status]}
                />
                <span className="l360-mono">
                  {formatDateShort(invoice.period_start)} – {formatDateShort(invoice.period_end)}
                </span>
              </p>

              <div style={{ overflowX: "auto", marginBottom: 16 }}>
                <table className="l360-table">
                  <thead>
                    <tr>
                      <th>Description</th>
                      <th>Qty</th>
                      <th>Unit price</th>
                      <th>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoice.lines.map((line) => (
                      <tr key={line.id}>
                        <td>{line.description}</td>
                        <td>{line.quantity}</td>
                        <td><Money cents={line.unit_price_cents} /></td>
                        <td><Money cents={line.amount_cents} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ marginTop: 8 }}>
                <a className="l360-link-btn" href={`/api/admin/invoices/${invoice.id}/pdf`}>
                  Download invoice PDF
                </a>
              </div>

              <p style={{ marginBottom: 16 }}>
                Total: <Money cents={invoice.total_cents} /> · Outstanding:{" "}
                <Money cents={invoice.outstanding_cents} />
              </p>

              {issueError && (
                <div className="l360-alert l360-alert-danger" role="alert">
                  ⚠ {issueError}
                </div>
              )}
              {issuedMessage && (
                <div className="l360-alert l360-alert-info" role="status">
                  {issuedMessage}
                </div>
              )}

              {confirmingIssue && invoice.status === "draft" ? (
                <>
                  <p style={{ marginBottom: 12 }}>
                    This assigns the invoice its number and emails it to{" "}
                    <strong>{invoice.client_label}</strong>. It can't be un-issued — only voided.
                  </p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <Button type="button" onClick={handleIssue} loading={issuing} loadingLabel="Issuing…">
                      Issue &amp; email
                    </Button>
                    <Button type="button" variant="secondary" disabled={issuing} onClick={() => setConfirmingIssue(false)}>
                      Back
                    </Button>
                  </div>
                </>
              ) : (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {invoice.status === "draft" && (
                    <Button type="button" onClick={() => setConfirmingIssue(true)}>
                      Issue invoice
                    </Button>
                  )}
                  <Button type="button" variant="secondary" onClick={close}>
                    Close
                  </Button>
                </div>
              )}
            </>
          )}

          {!loading && !invoice && !loadError && (
            <Button type="button" variant="secondary" onClick={onClose}>
              Close
            </Button>
          )}
        </Card>
    </Modal>
  );
}
