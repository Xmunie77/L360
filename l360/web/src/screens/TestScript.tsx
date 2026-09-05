import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Card, StatusBadge } from "../ui/ui";
import { ApiError, getTestScript, setTestMark, type TestScriptData } from "../api/client";
import { TEST_ITEM_COUNT, TEST_SECTIONS } from "./testScriptItems";
import type { Me } from "../api/client";

// Founder test-script screen — TEMPORARY (delete with testScriptItems.ts,
// routers/test_script.py and migration 0022 when testing wraps). Every
// tick and note saves to the server under the signed-in tester, so
// everyone — Simon included — watches the walkthrough fill in live.

interface MyMark {
  state: "pass" | "flag";
  note: string;
}

export function TestScript({ me }: { me: Me | null }) {
  const [mine, setMine] = useState<Record<string, MyMark>>({});
  const [others, setOthers] = useState<TestScriptData["testers"]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const noteTimers = useRef<Record<string, number>>({});

  async function refresh() {
    try {
      const data = await getTestScript();
      setOthers(data.testers);
      const my = data.testers.find((t) => t.user_id === data.my_user_id);
      const map: Record<string, MyMark> = {};
      for (const m of my?.marks ?? []) map[m.item_id] = { state: m.state as MyMark["state"], note: m.note ?? "" };
      setMine(map);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load the test script.");
    } finally {
      setLoaded(true);
    }
  }

  useEffect(() => {
    refresh();
    // Light polling keeps the progress chips honest while several people
    // test at once; the screen is temporary, so simple beats clever.
    const id = window.setInterval(refresh, 30_000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function save(itemId: string, mark: MyMark | null) {
    void setTestMark(itemId, mark?.state ?? null, mark?.note || null).catch(() =>
      setError("Couldn't save that tick — check your connection and tap it again."),
    );
  }

  function toggle(itemId: string, state: "pass" | "flag") {
    setMine((prev) => {
      const next = { ...prev };
      if (next[itemId]?.state === state) {
        delete next[itemId];
        save(itemId, null);
      } else {
        next[itemId] = { state, note: prev[itemId]?.note ?? "" };
        save(itemId, next[itemId]);
      }
      return next;
    });
  }

  function noteChanged(itemId: string, note: string) {
    setMine((prev) => {
      const cur = prev[itemId] ?? { state: "flag" as const, note: "" };
      const next = { ...prev, [itemId]: { ...cur, note } };
      window.clearTimeout(noteTimers.current[itemId]);
      noteTimers.current[itemId] = window.setTimeout(() => save(itemId, next[itemId]), 800);
      return next;
    });
  }

  const problems = useMemo(() => {
    const label = new Map(TEST_SECTIONS.flatMap((s) => s.items.map((i) => [i.id, i.do_] as const)));
    return others.flatMap((t) =>
      t.marks
        .filter((m) => m.state === "flag")
        .map((m) => ({ who: t.name, id: m.item_id, label: label.get(m.item_id) ?? m.item_id, note: m.note })),
    );
  }, [others]);

  return (
    <>
      <Card>
        <p style={{ marginTop: 0, maxWidth: "70ch" }}>
          The pre-launch walkthrough, {TEST_ITEM_COUNT} checks. Work top to bottom;{" "}
          <strong>Works</strong> = it behaved exactly as the grey text says, <strong>Problem</strong>{" "}
          = anything else — a note box appears, write what you saw. Everything saves under your name
          as you go, so there's nothing to send afterwards.
        </p>
        <p className="l360-field-hint" style={{ maxWidth: "70ch" }}>
          Tip: keep this list open on ONE device and do the testing on the other — laptop checks
          with the list on your phone, phone checks with the list on your laptop. Prefix everything
          you create with TEST and use an email you control.
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
          {others.map((t) => (
            <StatusBadge
              key={t.user_id}
              variant={t.user_id === (me?.id ?? -1) ? "info" : "pending"}
              label={`${t.name}: ${t.marks.length}/${TEST_ITEM_COUNT}`}
            />
          ))}
          {others.length === 0 && loaded && (
            <span className="l360-field-hint">No ticks from anyone yet — you're first.</span>
          )}
        </div>
      </Card>

      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}

      {problems.length > 0 && (
        <Card eyebrow="Across all testers" title="Problems reported">
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {problems.map((p, i) => (
              <li key={i} style={{ marginBottom: 6, maxWidth: "72ch" }}>
                <strong>
                  {p.who} · {p.id.toUpperCase()}
                </strong>{" "}
                — {p.label}
                {p.note ? <> — “{p.note}”</> : null}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {TEST_SECTIONS.map((section) => (
        <Card key={section.key} eyebrow={section.key} title={section.title}>
          {section.items.map((item) => {
            const mark = mine[item.id];
            return (
              <div
                key={item.id}
                style={{
                  borderTop: "1px solid var(--l360-lgrey)",
                  padding: "12px 0",
                  borderLeft: mark
                    ? `3px solid ${mark.state === "pass" ? "var(--l360-success, #1E6E45)" : "var(--l360-danger, #A93B2A)"}`
                    : "3px solid transparent",
                  paddingLeft: 10,
                }}
              >
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
                  <div style={{ flex: "1 1 320px", minWidth: 0 }}>
                    <p style={{ margin: "0 0 3px", fontWeight: 600 }}>
                      {item.id.toUpperCase()} — {item.do_}
                    </p>
                    <p className="l360-field-hint" style={{ margin: 0, maxWidth: "70ch" }}>{item.expect}</p>
                  </div>
                  <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                    <Button
                      type="button"
                      variant={mark?.state === "pass" ? "primary" : "secondary"}
                      onClick={() => toggle(item.id, "pass")}
                    >
                      Works
                    </Button>
                    <Button
                      type="button"
                      variant={mark?.state === "flag" ? "destructive" : "secondary"}
                      onClick={() => toggle(item.id, "flag")}
                    >
                      Problem
                    </Button>
                  </div>
                </div>
                {mark?.state === "flag" && (
                  <textarea
                    className="l360-textarea"
                    style={{ marginTop: 8 }}
                    rows={2}
                    placeholder="What did you do, and what did you see? Saved as you type."
                    value={mark.note}
                    onChange={(e) => noteChanged(item.id, e.target.value)}
                  />
                )}
              </div>
            );
          })}
        </Card>
      ))}

      <p className="l360-field-hint" style={{ maxWidth: "72ch" }}>
        Founder test script v2 · 05/09/2026 · this tab and its data are temporary and will be
        removed after testing. Anything that blocks you completely, message Simon straight away.
      </p>
    </>
  );
}
