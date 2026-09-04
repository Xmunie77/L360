import { useEffect, useState } from "react";
import { Button, Card, Input, Money, Select, StatusBadge, type StatusVariant } from "../ui/ui";
import { Billing, RunBilling } from "./Billing";
import { Reconciliation } from "./Reconciliation";
import {
  ApiError,
  getClientStatement,
  getEducatorSummary,
  listClients,
  listEducators,
  type Client,
  type ClientStatement,
  type Educator,
  type EducatorSummary,
  type Me,
} from "../api/client";
import { todayStr } from "../domain/datetime";

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return err.status === 403 ? "Admins only — you don't have access to this section." : err.detail;
  }
  return fallback;
}

function firstOfMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

interface StatementsProps {
  me: Me | null;
}

// Finance is the single home for money (Simon, 04/09/2026): Billing and
// Payments were separate top-level tabs and are now pills here, using the
// same sub-nav pattern as the Admin screen. Educators see no pill bar —
// only their own pay summary, exactly as before; the other two screens are
// admin-only server-side anyway.
type FinanceTab = "billing" | "statements" | "invoices" | "payments";

const FINANCE_TABS: { key: FinanceTab; label: string; hint: string }[] = [
  { key: "billing", label: "Billing", hint: "The monthly billing run — sweeps everything still unbilled into draft invoices" },
  { key: "statements", label: "Statements", hint: "Educator monthly pay summaries and per-learner statements" },
  { key: "invoices", label: "Invoices", hint: "Review, issue and void invoices" },
  { key: "payments", label: "Bank", hint: "Match incoming bank payments to invoices and record payments taken" },
];

export function Statements({ me }: StatementsProps) {
  const isAdmin = me?.role === "admin";
  const [tab, setTab] = useState<FinanceTab>("billing");

  if (!isAdmin) {
    // Educator view is unchanged: just their own monthly summary.
    return <EducatorSummaryCard me={me} />;
  }

  return (
    <>
      <Card>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {FINANCE_TABS.map((t) => (
            <Button
              key={t.key}
              type="button"
              variant={tab === t.key ? "primary" : "secondary"}
              title={t.hint}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </Button>
          ))}
        </div>
      </Card>

      {tab === "statements" && (
        <>
          <EducatorSummaryCard me={me} />
          <ClientStatementCard />
        </>
      )}
      {tab === "billing" && <RunBilling />}
      {tab === "invoices" && <Billing showRun={false} />}
      {tab === "payments" && <Reconciliation />}
    </>
  );
}

// --- educator monthly pay summary ------------------------------------------

function EducatorSummaryCard({ me }: { me: Me | null }) {
  const isAdmin = me?.role === "admin";
  const [educators, setEducators] = useState<Educator[]>([]);
  const [educatorId, setEducatorId] = useState<string>("");
  const [periodStart, setPeriodStart] = useState(firstOfMonth());
  const [periodEnd, setPeriodEnd] = useState(todayStr());
  const [summary, setSummary] = useState<EducatorSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAdmin) return;
    listEducators()
      .then(setEducators)
      .catch(() => setError("Couldn't load educators."));
  }, [isAdmin]);

  useEffect(() => {
    if (!me) return;
    const targetId = isAdmin ? educatorId : String(me.id);
    if (!targetId) {
      setSummary(null);
      return;
    }
    setLoading(true);
    setError(null);
    getEducatorSummary(Number(targetId), periodStart, periodEnd)
      .then(setSummary)
      .catch((err) => setError(errorMessage(err, "Couldn't load the summary.")))
      .finally(() => setLoading(false));
  }, [me, isAdmin, educatorId, periodStart, periodEnd]);

  return (
    <Card eyebrow="Pay" title={isAdmin ? "Educator monthly summary" : "Your monthly summary"}>
      <p style={{ marginBottom: 12 }}>
        Sessions delivered in the period and the rate they're paid at — use this to invoice
        Learning 360° Foundation.
      </p>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        {isAdmin && (
          <Select
            id="summary-educator"
            label="Educator"
            placeholder="Choose an educator…"
            options={educators.map((e) => ({ value: String(e.id), label: e.full_name }))}
            value={educatorId}
            onChange={(e) => setEducatorId(e.target.value)}
          />
        )}
        <Input id="summary-start" label="Period start" type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
        <Input id="summary-end" label="Period end" type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
      </div>

      {error && <p className="l360-alert l360-alert-danger">{error}</p>}
      {loading && <p className="l360-empty">Loading…</p>}
      {!loading && isAdmin && !educatorId && <p className="l360-empty">Choose an educator to see their summary.</p>}
      {!loading && summary && (
        <>
          <div style={{ overflowX: "auto" }}>
            <table className="l360-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Learner</th>
                  <th>Duration</th>
                  <th>Status</th>
                  <th>Rate</th>
                </tr>
              </thead>
              <tbody>
                {summary.sessions.length === 0 && (
                  <tr><td colSpan={5} className="l360-empty">No billable sessions in this period.</td></tr>
                )}
                {summary.sessions.map((s) => (
                  <tr key={s.booking_id}>
                    <td>{s.local_date}</td>
                    <td>{s.client_label}</td>
                    <td>{s.duration_minutes} min</td>
                    <td>{s.status.replace("_", " ")}</td>
                    <td><Money cents={s.rate_cents} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ marginTop: 12, fontWeight: 600 }}>
            Total payable: <Money cents={summary.total_payable_cents} />
          </p>
        </>
      )}
    </Card>
  );
}

// --- admin: client statement -----------------------------------------------

const STATEMENT_STATUS_VARIANT: Record<string, StatusVariant> = {
  draft: "pending",
  issued: "info",
  paid: "success",
  partially_paid: "info",
  void: "pending",
};

function ClientStatementCard() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [periodStart, setPeriodStart] = useState(firstOfMonth());
  const [periodEnd, setPeriodEnd] = useState(todayStr());
  const [statement, setStatement] = useState<ClientStatement | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listClients().then(setClients).catch(() => setError("Couldn't load learners."));
  }, []);

  useEffect(() => {
    if (!clientId) {
      setStatement(null);
      return;
    }
    setLoading(true);
    setError(null);
    getClientStatement(Number(clientId), periodStart, periodEnd)
      .then(setStatement)
      .catch((err) => setError(errorMessage(err, "Couldn't load the statement.")))
      .finally(() => setLoading(false));
  }, [clientId, periodStart, periodEnd]);

  return (
    <Card eyebrow="Finance" title="Learner statement">
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        <Select
          id="statement-client"
          label="Learner"
          placeholder="Choose a learner…"
          options={clients.map((c) => ({ value: String(c.id), label: `${c.guardian_first_name} ${c.guardian_surname}` }))}
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
        />
        <Input id="statement-start" label="Period start" type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
        <Input id="statement-end" label="Period end" type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
      </div>

      {error && <p className="l360-alert l360-alert-danger">{error}</p>}
      {loading && <p className="l360-empty">Loading…</p>}
      {!loading && !clientId && <p className="l360-empty">Choose a learner to see their statement.</p>}
      {!loading && statement && (
        <div style={{ overflowX: "auto" }}>
          <table className="l360-table">
            <tbody>
              <tr><td>Opening balance</td><td><Money cents={statement.opening_balance_cents} /></td></tr>
            </tbody>
          </table>

          <h3 style={{ marginTop: 20 }}>Invoices</h3>
          <table className="l360-table">
            <thead><tr><th>Number</th><th>Status</th><th>Issued</th><th>Total</th></tr></thead>
            <tbody>
              {statement.invoices.length === 0 && (
                <tr><td colSpan={4} className="l360-empty">None in this period.</td></tr>
              )}
              {statement.invoices.map((i) => (
                <tr key={i.id}>
                  <td>{i.number ?? "—"}</td>
                  <td><StatusBadge variant={STATEMENT_STATUS_VARIANT[i.status] ?? "pending"} label={i.status.replace("_", " ")} /></td>
                  <td>{i.issued_at ? i.issued_at.slice(0, 10) : "—"}</td>
                  <td><Money cents={i.total_cents} /></td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 style={{ marginTop: 20 }}>Payments</h3>
          <table className="l360-table">
            <thead><tr><th>Received</th><th>Method</th><th>Amount</th></tr></thead>
            <tbody>
              {statement.payments.length === 0 && (
                <tr><td colSpan={3} className="l360-empty">None in this period.</td></tr>
              )}
              {statement.payments.map((p) => (
                <tr key={p.id}>
                  <td>{p.received_at.slice(0, 10)}</td>
                  <td>{p.method.replace("_", " ")}</td>
                  <td><Money cents={p.amount_cents} /></td>
                </tr>
              ))}
            </tbody>
          </table>

          <p style={{ marginTop: 16, fontWeight: 600 }}>
            Closing balance: <Money cents={statement.closing_balance_cents} />
          </p>
        </div>
      )}
    </Card>
  );
}
