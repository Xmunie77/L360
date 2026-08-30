import { useState, type FormEvent } from "react";
import { Button, Card, Input } from "../ui/ui";
import { ApiError, changeMyPassword, type Me } from "../api/client";
import { CalendarFeedCard } from "./CalendarFeedCard";

// Profile: the signed-in user's own page — identity, self-service password
// change, and sign out. Replaces the name + Sign out band that used to sit
// in the nav (which ate a full row of the mobile header — Simon, 30/08/2026).

export function Profile({ me, onSignOut }: { me: Me | null; onSignOut: () => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    if (next.length < 8) {
      setError("The new password must be at least 8 characters.");
      return;
    }
    if (next !== confirm) {
      setError("The new passwords don't match.");
      return;
    }
    setSaving(true);
    try {
      await changeMyPassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      setMessage("Password changed.");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't change the password.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Card eyebrow="Account" title={me?.full_name ?? "Profile"}>
        <div style={{ overflowX: "auto" }}>
          <table className="l360-table">
            <tbody>
              <tr>
                <td style={{ width: "40%" }}>Email</td>
                <td>{me?.email ?? "—"}</td>
              </tr>
              <tr>
                <td>Role</td>
                <td style={{ textTransform: "capitalize" }}>{me?.role ?? "—"}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      <CalendarFeedCard />

      <Card eyebrow="Security" title="Change password">
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
        <form onSubmit={handleChangePassword} noValidate>
          <Input
            id="pw-current"
            label="Current password"
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <Input
              id="pw-new"
              label="New password"
              hint="At least 8 characters."
              type="password"
              autoComplete="new-password"
              required
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
            <Input
              id="pw-confirm"
              label="Confirm new password"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>
          <Button type="submit" loading={saving} loadingLabel="Saving…">
            Change password
          </Button>
        </form>
      </Card>

      <Card eyebrow="Session" title="Sign out">
        <p style={{ color: "var(--l360-bgrey)", marginBottom: 12 }}>
          Signed in as {me?.email ?? "—"}.
        </p>
        <Button type="button" variant="secondary" onClick={onSignOut}>
          Sign out
        </Button>
        <p style={{ color: "var(--l360-bgrey)", marginTop: 16, fontSize: "0.85rem" }}>
          Learning 360° Foundation · Swatar, Malta
        </p>
      </Card>
    </>
  );
}
