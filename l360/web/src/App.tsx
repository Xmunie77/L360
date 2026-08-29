import { useEffect, useState } from "react";
import { Wordmark } from "./ui/ui";
import { Calendar } from "./screens/Calendar";
import { Bookings } from "./screens/Bookings";
import { Clients } from "./screens/Clients";
import { Billing } from "./screens/Billing";
import { Reconciliation } from "./screens/Reconciliation";
import { Statements } from "./screens/Statements";
import { Admin } from "./screens/Admin";
import { ClientDetail } from "./screens/ClientDetail";
import { Login } from "./screens/Login";
import { EducatorFormView } from "./screens/EducatorFormView";
import { EducatorOnboarding } from "./screens/EducatorOnboarding";
import { Onboarding } from "./screens/Onboarding";
import { ResetPassword } from "./screens/ResetPassword";
import { getMe, getSession, logout, type Me } from "./api/client";

interface NavItem {
  key: string;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { key: "calendar", label: "Calendar" },
  { key: "bookings", label: "Bookings" },
  { key: "clients", label: "Learners" },
  { key: "billing", label: "Billing" },
  { key: "payments", label: "Payments" },
  { key: "statements", label: "Statements" },
  { key: "admin", label: "Admin" },
];

type AuthState = "loading" | "anon" | "authed";

// Router-free shell for the scaffold phase — state-based view switching,
// same approach as kitchentable/web's App.tsx. Swap for React Router once
// deep-linking (e.g. a booking permalink) is needed.
export function App() {
  const [active, setActive] = useState<string>(NAV_ITEMS[0].key);
  const [authState, setAuthState] = useState<AuthState>("loading");
  const [me, setMe] = useState<Me | null>(null);
  const [resetToken, setResetToken] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get("reset"),
  );
  // Public onboarding questionnaire (?onboarding=<token>) — guardians have
  // no account, so this renders before any auth check, like the reset flow.
  const [onboardingToken] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get("onboarding"),
  );
  const [educatorOnboardingToken] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get("educator-onboarding"),
  );
  const [educatorFormId] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get("educator-form"),
  );
  const [clientDetailId] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get("client"),
  );
  const activeLabel = NAV_ITEMS.find((n) => n.key === active)?.label ?? "";

  useEffect(() => {
    let cancelled = false;
    getSession()
      .then((s) => {
        if (cancelled) return;
        setAuthState(s.authed ? "authed" : "anon");
      })
      .catch(() => {
        if (!cancelled) setAuthState("anon");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (authState !== "authed") return;
    let cancelled = false;
    getMe()
      .then((m) => {
        if (!cancelled) setMe(m);
      })
      .catch(() => {
        // Session cookie may have expired between the /session check and
        // now — drop back to the login screen rather than show a broken shell.
        if (!cancelled) setAuthState("anon");
      });
    return () => {
      cancelled = true;
    };
  }, [authState]);

  async function handleSignOut() {
    try {
      await logout();
    } finally {
      setMe(null);
      setAuthState("anon");
      setActive(NAV_ITEMS[0].key);
    }
  }

  if (onboardingToken) {
    return <Onboarding token={onboardingToken} />;
  }

  if (educatorOnboardingToken) {
    return <EducatorOnboarding token={educatorOnboardingToken} />;
  }

  if (resetToken) {
    return (
      <ResetPassword
        token={resetToken}
        onDone={() => {
          window.history.replaceState(null, "", window.location.pathname);
          setResetToken(null);
        }}
      />
    );
  }

  if (authState === "loading") {
    return (
      <div className="l360-login-page">
        <p>Loading…</p>
      </div>
    );
  }

  if (authState === "anon") {
    return <Login onSignedIn={() => setAuthState("authed")} />;
  }

  if (clientDetailId) {
    return <ClientDetail id={Number(clientDetailId)} onClose={() => window.close()} />;
  }

  if (educatorFormId) {
    return <EducatorFormView userId={Number(educatorFormId)} onClose={() => window.close()} />;
  }

  return (
    <div className="l360-app">
      <a className="skip-link" href="#l360-main-content">Skip to main content</a>
      <nav className="l360-sidenav" aria-label="Primary">
        <Wordmark />
        <div className="l360-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              className="l360-nav-item"
              aria-current={item.key === active ? "page" : undefined}
              onClick={() => setActive(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="l360-nav-footer">
          {me && <div className="l360-nav-user">{me.full_name}</div>}
          <button type="button" className="l360-nav-signout" onClick={handleSignOut}>
            Sign out
          </button>
          <div className="l360-nav-org">Learning 360° Foundation · Swatar, Malta</div>
        </div>
      </nav>

      <div className="l360-main">
        <header className="l360-topbar">
          <h1>{activeLabel}</h1>
          <span className="l360-topbar-meta">Internal staff tool</span>
        </header>

        <main id="l360-main-content" className="l360-content">
          {active === "calendar" && <Calendar me={me} />}
          {active === "bookings" && <Bookings />}
          {active === "clients" && <Clients />}
          {active === "billing" && <Billing />}
          {active === "payments" && <Reconciliation />}
          {active === "statements" && <Statements me={me} />}
          {active === "admin" && <Admin />}
        </main>
      </div>
    </div>
  );
}
