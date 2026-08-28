import { useState, type FormEvent } from "react";
import { Button, Input, Wordmark } from "../ui/ui";
import { ApiError, login } from "../api/client";

export interface LoginProps {
  onSignedIn: () => void;
}

// Simple email/password gate in front of the app shell. No self-serve sign
// up — accounts are provisioned by an admin (see api.py /api/admin/users).
export function Login({ onSignedIn }: LoginProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      onSignedIn();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="l360-login-page">
      <form className="l360-login-card" onSubmit={handleSubmit} noValidate>
        <Wordmark className="l360-login-wordmark" />
        <p className="l360-login-intro">Sign in to manage rooms, bookings and clients.</p>

        {error && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {error}
          </div>
        )}

        <Input
          id="login-email"
          label="Email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          id="login-password"
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <Button type="submit" block loading={submitting} loadingLabel="Signing in…">
          Sign in
        </Button>
      </form>
    </div>
  );
}
