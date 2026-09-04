import { useEffect, useState } from "react";
import { Wordmark } from "./ui/ui";
import { Calendar } from "./screens/Calendar";
import { Bookings } from "./screens/Bookings";
import { ClientsAdmin } from "./screens/admin/ClientsAdmin";
import { UsersAdmin } from "./screens/admin/UsersAdmin";
import { Statements } from "./screens/Statements";
import { Admin } from "./screens/Admin";
import { ClientDetail } from "./screens/ClientDetail";
import { Login } from "./screens/Login";
import { Profile } from "./screens/Profile";
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
  { key: "bookings", label: "Sessions" },
  { key: "clients", label: "Learners" },
  { key: "educators", label: "Educators" },
  { key: "statements", label: "Finance" },
  { key: "admin", label: "Admin" },
  { key: "profile", label: "Profile" },
];

// Educators get a trimmed shell: their own sessions (Bookings), the shared
// room calendar for booking, their pay summary (Finance) and Profile. The
// hidden tabs are admin-only server-side anyway — this just stops them
// rendering as 403 dead ends.
const EDUCATOR_NAV_KEYS = new Set(["calendar", "bookings", "statements", "profile"]);

function navItemsFor(me: Me | null): NavItem[] {
  if (me && me.role !== "admin") return NAV_ITEMS.filter((n) => EDUCATOR_NAV_KEYS.has(n.key));
  return NAV_ITEMS;
}

// Where each role lands after sign-in: educators start on their own
// session list; admins on the Admin page (Simon, 03/09/2026).
function landingTabFor(me: Me): string {
  return me.role === "admin" ? "admin" : "bookings";
}

type AuthState = "loading" | "anon" | "authed";

// Router-free shell for the scaffold phase — state-based view switching,
// same approach as kitchentable/web's App.tsx. Swap for React Router once
// deep-linking (e.g. a booking permalink) is needed.
export function App() {
  const [active, setActive] = useState<string>(NAV_ITEMS[0].key);
  // Mobile-only left drawer for the tabs (Simon, 04/09/2026).
  const [navOpen, setNavOpen] = useState(false);
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
        if (cancelled) return;
        setMe(m);
        setActive(landingTabFor(m));
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

  // In a standalone PWA there is no browser chrome, so a detail page needs
  // its own way back — history if we have it, otherwise the app root with
  // the ?client=/?educator-form= param dropped (Simon, 04/09/2026).
  function goBackToApp() {
    if (window.history.length > 1) window.history.back();
    else window.location.assign("/");
  }

  if (clientDetailId) {
    return <ClientDetail id={Number(clientDetailId)} me={me} onClose={goBackToApp} />;
  }

  if (educatorFormId) {
    return <EducatorFormView userId={Number(educatorFormId)} onClose={goBackToApp} />;
  }

  return (
    <div className="l360-app">
      <a className="skip-link" href="#l360-main-content">Skip to main content</a>
      {navOpen && (
        <button
          type="button"
          className="l360-drawer-backdrop"
          aria-label="Close menu"
          onClick={() => setNavOpen(false)}
        />
      )}
      <nav className={navOpen ? "l360-sidenav open" : "l360-sidenav"} aria-label="Primary">
        <Wordmark />
        <div className="l360-nav">
          {navItemsFor(me).map((item) => (
            <button
              key={item.key}
              type="button"
              className="l360-nav-item"
              aria-current={item.key === active ? "page" : undefined}
              onClick={() => {
                setActive(item.key);
                setNavOpen(false);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>

      </nav>

      <div className="l360-main">
        <header className="l360-topbar">
          <button
            type="button"
            className="l360-menu-btn"
            aria-label="Open menu"
            aria-expanded={navOpen}
            onClick={() => setNavOpen(true)}
          >
            ☰
          </button>
          <h1>{activeLabel}</h1>
          <span className="l360-topbar-meta">Internal staff tool</span>
        </header>

        <main id="l360-main-content" className="l360-content">
          {active === "calendar" && <Calendar me={me} />}
          {active === "bookings" && <Bookings me={me} />}
          {active === "clients" && <ClientsAdmin />}
          {active === "educators" && <UsersAdmin />}
          {active === "statements" && <Statements me={me} />}
          {active === "admin" && <Admin />}
          {active === "profile" && <Profile me={me} onSignOut={handleSignOut} />}
        </main>
      </div>
    </div>
  );
}
