import { useState, type FormEvent } from "react";
import { Button, Input, Wordmark } from "../ui/ui";
import { ApiError, resetPassword } from "../api/client";

export interface ResetPasswordProps {
  token: string;
  onDone: () => void;
}

// Landing screen for the link emailed by /api/forgot-password. Reachable
// whether or not the visitor has a session — the token itself is the auth.
export function ResetPassword({ token, onDone }: ResetPasswordProps) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setSubmitting(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="l360-login-page">
        <div className="l360-login-card">
          <Wordmark className="l360-login-wordmark" />
          <div className="l360-alert l360-alert-info" role="status">
            Password updated. You can sign in now.
          </div>
          <Button type="button" block onClick={onDone}>
            Go to sign in
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="l360-login-page">
      <form className="l360-login-card" onSubmit={handleSubmit} noValidate>
        <Wordmark className="l360-login-wordmark" />
        <p className="l360-login-intro">Choose a new password.</p>

        {error && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {error}
          </div>
        )}

        <Input
          id="reset-password"
          label="New password"
          hint="At least 8 characters."
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Input
          id="reset-password-confirm"
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />

        <Button type="submit" block loading={submitting} loadingLabel="Saving…">
          Set new password
        </Button>
      </form>
    </div>
  );
}
