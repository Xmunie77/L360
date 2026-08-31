import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Input, Textarea } from "../../ui/ui";
import {
  adminGetInvoiceSettings,
  adminSaveInvoiceSettings,
  type InvoiceSettings,
} from "../../api/client";
import { errorMessage } from "./shared";

// --- invoice template settings ---------------------------------------------

export function InvoiceSettingsAdmin() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [f, setF] = useState<InvoiceSettings>({ name: "", address: "", vat: "", bank: "", contact: "", footer: "" });

  useEffect(() => {
    adminGetInvoiceSettings()
      .then(setF)
      .catch((err) => setError(errorMessage(err, "Couldn't load the invoice settings.")))
      .finally(() => setLoading(false));
  }, []);

  function set(key: keyof InvoiceSettings, value: string) {
    setF((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setSaving(true);
    try {
      setF(await adminSaveInvoiceSettings(f));
      setMessage("Saved. Use “View sample invoice” to check the result.");
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the invoice settings."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card eyebrow="System" title="Invoice template">
      <p style={{ color: "var(--l360-bgrey)", marginBottom: 16 }}>
        The letterhead printed on every client invoice PDF. One line per row
        for the address, bank and contact blocks. Invoice numbering is set
        separately and isn’t part of the template.
      </p>
      {error && <div className="l360-alert l360-alert-danger" role="alert">⚠ {error}</div>}
      {message && <div className="l360-alert l360-alert-info" role="status">{message}</div>}
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : (
        <form onSubmit={handleSave} noValidate>
          <Input id="inv-name" label="Foundation name" value={f.name} onChange={(e) => set("name", e.target.value)} />
          <Textarea id="inv-address" label="Address" rows={2} value={f.address} onChange={(e) => set("address", e.target.value)} />
          <Input id="inv-vat" label="VAT / registration line" value={f.vat} onChange={(e) => set("vat", e.target.value)} />
          <Textarea id="inv-bank" label="Bank details" rows={3} value={f.bank} onChange={(e) => set("bank", e.target.value)} />
          <Textarea id="inv-contact" label="Contact lines" rows={2} value={f.contact} onChange={(e) => set("contact", e.target.value)} />
          <Textarea
            id="inv-footer"
            label="Footer note"
            hint="Optional — e.g. payment terms. Shown in small print under the totals."
            rows={2}
            value={f.footer}
            onChange={(e) => set("footer", e.target.value)}
          />
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <Button type="submit" loading={saving} loadingLabel="Saving…">
              Save settings
            </Button>
            <a className="l360-link-btn" href="/api/admin/invoice-settings/sample-pdf" target="_blank" rel="noopener noreferrer">
              View sample invoice
            </a>
          </div>
        </form>
      )}
    </Card>
  );
}
