import { useEffect, useState } from "react";
import { Button, Card } from "../../ui/ui";
import {
  adminListFacilityHours,
  adminUpsertFacilityHours,
} from "../../api/client";
import { errorMessage, WEEKDAY_LABEL } from "./shared";

// --- facility hours ----------------------------------------------------

function timeToInput(t: string): string {
  return t.slice(0, 5);
}

function timeToApi(t: string): string {
  return t.length === 5 ? `${t}:00` : t;
}

export function FacilityHoursAdmin() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<number, { open: string; close: string }>>({});
  const [busyDay, setBusyDay] = useState<number | null>(null);
  // Per-day, not a single value — saving one day must not clear the
  // "Saved" confirmation off every other day that was already saved.
  const [savedDays, setSavedDays] = useState<Set<number>>(new Set());

  function editDraft(weekday: number, field: "open" | "close", value: string) {
    setDrafts((d) => ({ ...d, [weekday]: { ...d[weekday], [field]: value } }));
    setSavedDays((prev) => {
      if (!prev.has(weekday)) return prev;
      const next = new Set(prev);
      next.delete(weekday);
      return next;
    });
  }

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const hours = await adminListFacilityHours();
      const map = new Map(hours.map((h) => [h.weekday, h] as const));
      const nextDrafts: Record<number, { open: string; close: string }> = {};
      for (let d = 0; d < 7; d++) {
        const existing = map.get(d);
        nextDrafts[d] = {
          open: existing ? timeToInput(existing.open_time) : "09:00",
          close: existing ? timeToInput(existing.close_time) : "17:00",
        };
      }
      setDrafts(nextDrafts);
    } catch (err) {
      setError(errorMessage(err, "Couldn't load facility hours."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleSave(weekday: number) {
    const draft = drafts[weekday];
    if (!draft) return;
    setBusyDay(weekday);
    setError(null);
    try {
      await adminUpsertFacilityHours({
        weekday,
        open_time: timeToApi(draft.open),
        close_time: timeToApi(draft.close),
      });
      setSavedDays((prev) => new Set(prev).add(weekday));
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save these hours."));
    } finally {
      setBusyDay(null);
    }
  }

  return (
    <Card eyebrow="Facilities" title="Facility hours">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Day</th>
                <th>Open</th>
                <th>Close</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {WEEKDAY_LABEL.map((label, weekday) => {
                const draft = drafts[weekday] ?? { open: "09:00", close: "17:00" };
                return (
                  <tr key={weekday}>
                    <td>{label}</td>
                    <td>
                      <input
                        className="l360-input"
                        type="time"
                        aria-label={`${label} open time`}
                        value={draft.open}
                        onChange={(e) => editDraft(weekday, "open", e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        className="l360-input"
                        type="time"
                        aria-label={`${label} close time`}
                        value={draft.close}
                        onChange={(e) => editDraft(weekday, "close", e.target.value)}
                      />
                    </td>
                    <td>
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => handleSave(weekday)}
                        loading={busyDay === weekday}
                        loadingLabel="Saving…"
                      >
                        {savedDays.has(weekday) ? "Saved" : "Save"}
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
