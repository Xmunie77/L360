import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Input, Money, Select } from "../ui/ui";
import {
  ApiError,
  listInvoices,
  listUnmatchedTxns,
  manualMatchPayment,
  adminListUsers,
  recordPayment,
  syncPayments,
  type AdminUser,
  type BankTxn,
  type Invoice,
  type PaymentMethod,
  type SyncResult,
} from "../api/client";

const REVOLUT_NOT_CONFIGURED = "REVOLUT_API_TOKEN is not set";

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return err.status === 403 ? "Admins only — you don't have access to this section." : err.detail;
  }
  return fallback;
}

function invoiceLabel(inv: Invoice): string {
  const period = `${inv.period_start} – ${inv.period_end}`;
  return inv.number ? `${inv.number} · ${inv.client_label} (${period})` : `${inv.client_label} (${period})`;
}

// Bank reconciliation: pull Revolut Business transactions, auto-match what
// the backend can, then let staff hand-match what's left or record a
// cash/manual bank payment directly against an invoice.
export function Reconciliation() {
  const [unmatched, setUnmatched] = useState<BankTxn[]>([]);
  const [openInvoices, setOpenInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  async function refresh() {
    setLoading(true);
    setLoadError(null);
    try {
      const [txns, issued, partial] = await Promise.all([
        listUnmatchedTxns(),
        listInvoices({ status: "issued" }),
        listInvoices({ status: "partially_paid" }),
      ]);
      setUnmatched(txns);
      setOpenInvoices([...issued, ...partial]);
      setForbidden(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setForbidden(true);
      setLoadError(errorMessage(err, "Couldn't load payments data."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  if (forbidden) {
    return (
      <Card eyebrow="Finance" title="Payments">
        <p className="l360-empty">Admins only — you don't have access to this section.</p>
      </Card>
    );
  }

  return (
    <>
      <SyncPanel onSynced={refresh} />

      <Card eyebrow="Finance" title="Unmatched transactions">
        {loadError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {loadError}
          </div>
        )}

        {loading ? (
          <p className="l360-empty">Loading…</p>
        ) : unmatched.length === 0 ? (
          <p className="l360-empty">Nothing unmatched.</p>
        ) : (
          /* A work queue, not a reference table — as a 5-column table the
             invoice picker sat hundreds of pixels off-screen on a phone
             (04/09/2026 UI audit). One card per transaction instead. */
          <div>
            {unmatched.map((txn) => (
              <UnmatchedRow key={txn.id} txn={txn} openInvoices={openInvoices} onMatched={refresh} />
            ))}
          </div>
        )}
      </Card>

      <RecordPaymentPanel openInvoices={openInvoices} onRecorded={refresh} />
    </>
  );
}

// --- sync panel ------------------------------------------------------------

function SyncPanel({ onSynced }: { onSynced: () => void }) {
  const [syncing, setSyncing] = useState(false);
  const [result, setResult] = useState<SyncResult | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSync() {
    setSyncing(true);
    setError(null);
    setResult(null);
    setNotConfigured(false);
    try {
      const res = await syncPayments();
      setResult(res);
      onSynced();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && err.detail === REVOLUT_NOT_CONFIGURED) {
        setNotConfigured(true);
      } else {
        setError(errorMessage(err, "Couldn't sync payments."));
      }
    } finally {
      setSyncing(false);
    }
  }

  return (
    <Card eyebrow="Finance" title="Sync payments">
      <p style={{ marginBottom: 16 }}>Pulls new Revolut Business transfers and auto-matches them to invoices by reference.</p>

      {notConfigured && (
        <div className="l360-alert l360-alert-info" role="status">
          Revolut isn't connected yet — set REVOLUT_API_TOKEN to enable automatic syncing. Use "Record
          payment" below for now.
        </div>
      )}
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {result && (
        <div className="l360-alert l360-alert-info" role="status">
          Imported {result.imported}, matched {result.matched}, unmatched {result.unmatched}.
        </div>
      )}

      <Button type="button" variant="secondary" onClick={handleSync} loading={syncing} loadingLabel="Syncing…">
        Sync payments
      </Button>
    </Card>
  );
}

// --- unmatched row -----------------------------------------------------

interface UnmatchedRowProps {
  txn: BankTxn;
  openInvoices: Invoice[];
  onMatched: () => void;
}

function UnmatchedRow({ txn, openInvoices, onMatched }: UnmatchedRowProps) {
  const [invoiceId, setInvoiceId] = useState("");
  const [matching, setMatching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleMatch() {
    if (!invoiceId) return;
    setError(null);
    setMatching(true);
    try {
      await manualMatchPayment(txn.id, Number(invoiceId));
      onMatched();
    } catch (err) {
      setError(errorMessage(err, "Couldn't match this transaction."));
    } finally {
      setMatching(false);
    }
  }

  return (
    <div className="l360-session-card">
      <div className="l360-session-card-top">
        <span style={{ fontWeight: 600 }}>
          <Money cents={txn.amount_cents} /> · {new Date(txn.txn_date).toLocaleDateString("en-GB")}
        </span>
      </div>
      <p className="l360-field-hint" style={{ margin: "2px 0 8px" }}>
        {txn.reference ?? "No reference"} · {txn.counterparty ?? "Unknown counterparty"}
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 220px", minWidth: 0 }}>
          <Select
            id={`match-invoice-${txn.id}`}
            label="Match to invoice"
            error={error ?? undefined}
            placeholder="Choose an invoice…"
            value={invoiceId}
            onChange={(e) => setInvoiceId(e.target.value)}
            options={openInvoices.map((inv) => ({ value: String(inv.id), label: invoiceLabel(inv) }))}
          />
        </div>
        <div style={{ marginBottom: 16 }}>
          <Button
            type="button"
            variant="secondary"
            onClick={handleMatch}
            disabled={!invoiceId}
            loading={matching}
            loadingLabel="Matching…"
          >
            Match
          </Button>
        </div>
      </div>
    </div>
  );
}

// --- record payment panel -----------------------------------------------

function RecordPaymentPanel({ openInvoices, onRecorded }: { openInvoices: Invoice[]; onRecorded: () => void }) {
  const [invoiceId, setInvoiceId] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<PaymentMethod>("bank_transfer");
  const [receivedAt, setReceivedAt] = useState("");
  const [receivedById, setReceivedById] = useState("");
  const [staff, setStaff] = useState<AdminUser[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    adminListUsers()
      .then((users) => setStaff(users.filter((u) => u.active)))
      .catch(() => {});
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!invoiceId || !amount || !receivedAt) {
      setError("Choose an invoice, amount and date received.");
      return;
    }
    if (method === "cash" && !receivedById) {
      setError("Please record who received the cash.");
      return;
    }
    setError(null);
    setSuccess(false);
    setSubmitting(true);
    try {
      const cents = Math.round(Number(amount) * 100);
      await recordPayment({
        invoice_id: Number(invoiceId),
        amount_cents: cents,
        method,
        received_at: new Date(`${receivedAt}T00:00:00`).toISOString(),
        received_by_id: method === "cash" ? Number(receivedById) : null,
      });
      setSuccess(true);
      setAmount("");
      setInvoiceId("");
      setReceivedAt("");
      onRecorded();
    } catch (err) {
      setError(errorMessage(err, "Couldn't record this payment."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card eyebrow="Finance" title="Record payment">
      <p style={{ marginBottom: 16 }}>For cash, or a bank transfer that doesn't need Revolut matching.</p>
      <form onSubmit={handleSubmit} noValidate>
        {error && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {error}
          </div>
        )}
        {success && (
          <div className="l360-alert l360-alert-info" role="status">
            Payment recorded.
          </div>
        )}

        <Select
          id="record-payment-invoice"
          label="Invoice"
          required
          placeholder="Choose an invoice…"
          value={invoiceId}
          onChange={(e) => setInvoiceId(e.target.value)}
          options={openInvoices.map((inv) => ({ value: String(inv.id), label: invoiceLabel(inv) }))}
        />
        <Input
          id="record-payment-amount"
          label="Amount (€)"
          type="number"
          step="0.01"
          min="0.01"
          required
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <Select
          id="record-payment-method"
          label="Method"
          required
          value={method}
          onChange={(e) => setMethod(e.target.value as PaymentMethod)}
          options={[
            { value: "bank_transfer", label: "Bank transfer" },
            { value: "cash", label: "Cash" },
          ]}
        />
        {method === "cash" && (
          <Select
            id="record-payment-received-by"
            label="Received by"
            hint="Who physically took the cash."
            required
            placeholder="Choose a staff member…"
            value={receivedById}
            onChange={(e) => setReceivedById(e.target.value)}
            options={staff.map((u) => ({ value: String(u.id), label: u.full_name }))}
          />
        )}
        <Input
          id="record-payment-date"
          label="Date received"
          type="date"
          required
          value={receivedAt}
          onChange={(e) => setReceivedAt(e.target.value)}
        />

        <Button type="submit" loading={submitting} loadingLabel="Recording…">
          Record payment
        </Button>
      </form>
    </Card>
  );
}
