import { useEffect, useState } from "react";
import { Button, Card, Input } from "../ui/ui";
import {
  ApiError,
  createOrRotateCalendarToken,
  getMyCalendarToken,
  revokeCalendarToken,
  type CalendarToken,
} from "../api/client";

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

// Personal iCal subscribe/rotate/revoke card. Lived on Statements until
// 30/08/2026; now rendered on the Profile page (it's about YOUR calendar,
// not the foundation's finances).
export function CalendarFeedCard() {
  const [token, setToken] = useState<CalendarToken | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setToken(await getMyCalendarToken());
    } catch (err) {
      setError(errorMessage(err, "Couldn't load your calendar link."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      setToken(await createOrRotateCalendarToken());
    } catch (err) {
      setError(errorMessage(err, "Couldn't create your calendar link."));
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke() {
    setBusy(true);
    setError(null);
    try {
      await revokeCalendarToken();
      setToken(null);
    } catch (err) {
      setError(errorMessage(err, "Couldn't revoke your calendar link."));
    } finally {
      setBusy(false);
    }
  }

  const feedUrl = token ? `${window.location.origin}${token.feed_path}` : null;

  return (
    <Card eyebrow="Your calendar" title="Subscribe to your sessions">
      <p style={{ marginBottom: 12 }}>
        A read-only link you can add to Google, Apple or Outlook calendar so your confirmed
        sessions show up alongside your personal calendar. Anyone with this link can see your
        session times — revoke and create a new one if it ever leaks.
      </p>
      {loading && <p className="l360-empty">Loading…</p>}
      {error && <p className="l360-alert l360-alert-danger">{error}</p>}
      {!loading && !feedUrl && (
        <Button variant="primary" onClick={handleCreate} loading={busy} loadingLabel="Creating…">
          Get my calendar link
        </Button>
      )}
      {!loading && feedUrl && (
        <>
          <Input
            id="calendar-feed-url"
            label="Feed URL"
            hint="Tap “Add to my calendar” on iPhone/Mac or Outlook. On Android/Google Calendar, tap this field to select the link, then paste it into “From URL”."
            readOnly
            value={feedUrl}
            onFocus={(e) => e.currentTarget.select()}
          />
          <div style={{ display: "flex", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
            {/* webcal:// hands the feed straight to Apple Calendar / Outlook —
                one tap instead of copy-paste. Google Calendar ignores the
                scheme, so the URL field above stays for Android/Google.
                (Simon, 04/09/2026.) */}
            <a className="l360-btn l360-btn-primary" href={feedUrl.replace(/^https?:/, "webcal:")}>
              Add to my calendar
            </a>
            <Button variant="secondary" onClick={handleCreate} loading={busy} loadingLabel="Rotating…">
              Get a new link
            </Button>
            <Button variant="destructive" onClick={handleRevoke} loading={busy} loadingLabel="Revoking…">
              Revoke
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}
