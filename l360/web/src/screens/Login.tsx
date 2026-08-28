import { useState, type FormEvent } from "react";
import { Button, Input, Wordmark } from "../ui/ui";
import { ApiError, forgotPassword, login } from "../api/client";

export interface LoginProps {
  onSignedIn: () => void;
}

// Simple email/password gate in front of the app shell. No self-serve sign
// up — accounts are provisioned by an admin (see api.py /api/admin/users).
export function Login({ onSignedIn }: LoginProps) {
  const [mode, setMode] = useState<"signin" | "forgot">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [forgotSent, setForgotSent] = useState(false);

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

  async function handleForgotSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await forgotPassword(email);
      setForgotSent(true);
    } catch {
      // The endpoint always returns ok — a network failure is the only way
      // here, so a generic message is accurate rather than misleading.
      setError("Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (mode === "forgot") {
    return (
      <div className="l360-login-page">
        <form className="l360-login-card" onSubmit={handleForgotSubmit} noValidate>
          <Wordmark className="l360-login-wordmark" />
          <p className="l360-login-intro">
            Enter your email and we'll send you a link to reset your password.
          </p>

          {error && (
            <div className="l360-alert l360-alert-danger" role="alert">
              ⚠ {error}
            </div>
          )}
          {forgotSent && (
            <div className="l360-alert l360-alert-info" role="status">
              If that email has an account, a reset link is on its way. Check your inbox.
            </div>
          )}

          {!forgotSent && (
            <>
              <Input
                id="forgot-email"
                label="Email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <Button type="submit" block loading={submitting} loadingLabel="Sending…">
                Send reset link
              </Button>
            </>
          )}

          <button
            type="button"
            className="l360-link-btn"
            onClick={() => {
              setMode("signin");
              setError(null);
              setForgotSent(false);
            }}
          >
            Back to sign in
          </button>
        </form>
      </div>
    );
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

        <button
          type="button"
          className="l360-link-btn"
          onClick={() => {
            setMode("forgot");
            setError(null);
          }}
        >
          Forgot password?
        </button>
      </form>
    </div>
  );
}
