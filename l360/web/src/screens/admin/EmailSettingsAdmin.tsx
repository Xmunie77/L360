import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Input } from "../../ui/ui";
import {
  adminGetEmailSettings,
  adminSaveEmailSettings,
  adminTestEmail,
} from "../../api/client";
import { errorMessage } from "./shared";

// --- email (SMTP) settings --------------------------------------------------

export function EmailSettingsAdmin() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [host, setHost] = useState("");
  const [port, setPort] = useState("587");
  const [user, setUser] = useState("");
  const [emailFrom, setEmailFrom] = useState("");
  const [password, setPassword] = useState("");
  const [passwordSet, setPasswordSet] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    adminGetEmailSettings()
      .then((s) => {
        setHost(s.host);
        setPort(String(s.port));
        setUser(s.user);
        setEmailFrom(s.email_from);
        setPasswordSet(s.password_set);
      })
      .catch((err) => setError(errorMessage(err, "Couldn't load the email settings.")))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    const portNum = Number(port);
    if (!Number.isInteger(portNum) || portNum < 1 || portNum > 65535) {
      setError("Port must be a number between 1 and 65535 (Gmail uses 587).");
      return;
    }
    setSaving(true);
    try {
      const saved = await adminSaveEmailSettings({
        host: host.trim(),
        port: portNum,
        user: user.trim(),
        email_from: emailFrom.trim(),
        password: password || null,
      });
      setPasswordSet(saved.password_set);
      setPassword("");
      setMessage("Saved. Use “Send test email” to confirm sending works.");
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the email settings."));
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setError(null);
    setMessage(null);
    setTesting(true);
    try {
      const r = await adminTestEmail();
      if (r.ok) {
        setMessage(r.detail);
      } else {
        setError(r.detail);
      }
    } catch (err) {
      setError(errorMessage(err, "Couldn't send the test email."));
    } finally {
      setTesting(false);
    }
  }

  return (
    <Card eyebrow="System" title="Email sending">
      <p style={{ color: "var(--l360-bgrey)", marginBottom: 16 }}>
        Used for onboarding invites, booking confirmations, reminders and invoices.
        For a Gmail / Google Workspace mailbox use host smtp.gmail.com, port 587, and a
        Google App Password (not the mailbox password — create one at
        myaccount.google.com/apppasswords with 2-Step Verification switched on).
      </p>
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {message && (
        <div className="l360-alert l360-alert-info" role="status">
          {message}
        </div>
      )}
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : (
        <form onSubmit={handleSave} noValidate>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <Input id="email-host" label="SMTP host" hint="smtp.gmail.com for Google Workspace" value={host} onChange={(e) => setHost(e.target.value)} />
            <Input id="email-port" label="Port" inputMode="numeric" value={port} onChange={(e) => setPort(e.target.value)} />
          </div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <Input id="email-user" label="Username (email address)" type="email" value={user} onChange={(e) => setUser(e.target.value)} />
            <Input id="email-from" label="From address" hint="Usually the same address" type="email" value={emailFrom} onChange={(e) => setEmailFrom(e.target.value)} />
          </div>
          <Input
            id="email-password"
            label="App password"
            type="password"
            autoComplete="new-password"
            hint={passwordSet ? "A password is saved — leave blank to keep it, type to replace it. It is never shown again." : "No password saved yet."}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button type="submit" loading={saving} loadingLabel="Saving…">
              Save settings
            </Button>
            <Button type="button" variant="secondary" onClick={handleTest} loading={testing} loadingLabel="Sending…">
              Send test email
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
