import { useEffect, useState } from "react";
import { Card } from "../../ui/ui";
import {
  adminDeleteFacilityHours,
  adminListFacilityHours,
  adminUpsertFacilityHours,
} from "../../api/client";
import { errorMessage, WEEKDAY_LABEL } from "./shared";

// --- facility hours ----------------------------------------------------
// One row per weekday: an Open toggle (off = closed, no bookings that day)
// and, when open, the open/close times. Everything saves itself — the old
// per-row Save/Saved buttons confused people (03/09/2026, Simon).

const DEFAULT_OPEN = "08:00";
const DEFAULT_CLOSE = "19:00";

function timeToInput(t: string): string {
  return t.slice(0, 5);
}

function timeToApi(t: string): string {
  return t.length === 5 ? `${t}:00` : t;
}

type DayDraft = { set: boolean; open: string; close: string };

export function FacilityHoursAdmin() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<number, DayDraft>>({});
  // Days with an in-flight request — their controls disable briefly.
  const [busyDays, setBusyDays] = useState<Set<number>>(new Set());

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const hours = await adminListFacilityHours();
      const map = new Map(hours.map((h) => [h.weekday, h] as const));
      const next: Record<number, DayDraft> = {};
      for (let d = 0; d < 7; d++) {
        const existing = map.get(d);
        next[d] = existing
          ? { set: true, open: timeToInput(existing.open_time), close: timeToInput(existing.close_time) }
          : { set: false, open: DEFAULT_OPEN, close: DEFAULT_CLOSE };
      }
      setDrafts(next);
    } catch (err) {
      setError(errorMessage(err, "Couldn't load facility hours."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function markBusy(weekday: number, busy: boolean) {
    setBusyDays((prev) => {
      const next = new Set(prev);
      if (busy) next.add(weekday);
      else next.delete(weekday);
      return next;
    });
  }

  async function persist(weekday: number, draft: DayDraft) {
    markBusy(weekday, true);
    setError(null);
    try {
      if (draft.set) {
        await adminUpsertFacilityHours({
          weekday,
          open_time: timeToApi(draft.open),
          close_time: timeToApi(draft.close),
        });
      } else {
        await adminDeleteFacilityHours(weekday);
      }
    } catch (err) {
      setError(errorMessage(err, "Couldn't save these hours."));
      await refresh();
    } finally {
      markBusy(weekday, false);
    }
  }

  function handleToggle(weekday: number, set: boolean) {
    const draft = { ...(drafts[weekday] ?? { set: false, open: DEFAULT_OPEN, close: DEFAULT_CLOSE }), set };
    setDrafts((d) => ({ ...d, [weekday]: draft }));
    void persist(weekday, draft);
  }

  function handleTime(weekday: number, field: "open" | "close", value: string) {
    if (!value) return; // cleared mid-edit — wait for a real time
    const draft = { ...drafts[weekday], [field]: value };
    setDrafts((d) => ({ ...d, [weekday]: draft }));
    void persist(weekday, draft);
  }

  return (
    <Card eyebrow="Facilities" title="Facility hours">
      <p className="l360-field-hint" style={{ marginTop: 0 }}>
        Days switched off are closed — no sessions can be booked on them. Changes save automatically.
      </p>
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
                <th>Open?</th>
                <th>Opens</th>
                <th>Closes</th>
              </tr>
            </thead>
            <tbody>
              {WEEKDAY_LABEL.map((label, weekday) => {
                const draft = drafts[weekday] ?? { set: false, open: DEFAULT_OPEN, close: DEFAULT_CLOSE };
                const busy = busyDays.has(weekday);
                return (
                  <tr key={weekday}>
                    <td>{label}</td>
                    <td>
                      <label style={{ display: "inline-flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          aria-label={`${label} open`}
                          checked={draft.set}
                          disabled={busy}
                          onChange={(e) => handleToggle(weekday, e.target.checked)}
                          style={{ width: 20, height: 20 }}
                        />
                        <span>{draft.set ? "Open" : "Closed"}</span>
                      </label>
                    </td>
                    <td>
                      {draft.set ? (
                        <input
                          className="l360-input"
                          type="time"
                          aria-label={`${label} open time`}
                          value={draft.open}
                          disabled={busy}
                          onChange={(e) => handleTime(weekday, "open", e.target.value)}
                        />
                      ) : (
                        <span className="l360-field-hint">–</span>
                      )}
                    </td>
                    <td>
                      {draft.set ? (
                        <input
                          className="l360-input"
                          type="time"
                          aria-label={`${label} close time`}
                          value={draft.close}
                          disabled={busy}
                          onChange={(e) => handleTime(weekday, "close", e.target.value)}
                        />
                      ) : (
                        <span className="l360-field-hint">–</span>
                      )}
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
