import { useEffect, useState } from "react";
import { Button, Card, Input, StatusBadge, Textarea } from "../../ui/ui";
import {
  adminListEmailTemplates,
  adminResetEmailTemplate,
  adminSaveEmailTemplate,
  type EmailTemplate,
} from "../../api/client";
import { errorMessage } from "./shared";

// Editable wording for every email the system sends by itself. The card is
// a compact list — one row per template — and the editor opens in a modal
// (Simon, 04/09/2026: "use modals … otherwise the page will be too long").
// "Reset to default" restores the built-in wording (the backend clears the
// override rows).

function TemplateEditorModal({
  tpl,
  onSaved,
  onClose,
}: {
  tpl: EmailTemplate;
  onSaved: (t: EmailTemplate) => void;
  onClose: () => void;
}) {
  const [subject, setSubject] = useState(tpl.subject);
  const [body, setBody] = useState(tpl.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = subject !== tpl.subject || body !== tpl.body;

  async function run(action: () => Promise<EmailTemplate>, failMsg: string) {
    setBusy(true);
    setError(null);
    try {
      const saved = await action();
      onSaved(saved);
      onClose();
    } catch (err) {
      setError(errorMessage(err, failMsg));
      setBusy(false);
    }
  }

  return (
    <div className="l360-modal-backdrop" onClick={onClose}>
      <div className="l360-modal-card" onClick={(e) => e.stopPropagation()}>
        <Card eyebrow="Automated email" title={tpl.label}>
          <p style={{ color: "var(--l360-bgrey)", marginTop: 0 }}>{tpl.description}</p>
          {error && (
            <div className="l360-alert l360-alert-danger" role="alert">
              ⚠ {error}
            </div>
          )}
          <Input
            id={`tpl-subject-${tpl.kind}`}
            label="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          />
          <Textarea
            id={`tpl-body-${tpl.kind}`}
            label="Body"
            rows={Math.min(14, Math.max(5, body.split("\n").length + 1))}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <p className="l360-field-hint" style={{ marginTop: 0 }}>
            You can use:{" "}
            {tpl.placeholders.map(([name, meaning], i) => (
              <span key={name}>
                {i > 0 && " · "}
                <code>{`{${name}}`}</code> {meaning}
              </span>
            ))}
            . These are filled in automatically for each recipient; anything else stays as
            literal text.
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button
              type="button"
              disabled={!dirty}
              loading={busy}
              loadingLabel="Saving…"
              onClick={() =>
                void run(
                  () => adminSaveEmailTemplate(tpl.kind, subject, body),
                  "Couldn't save the template.",
                )
              }
            >
              Save wording
            </Button>
            {(tpl.is_custom || dirty) && (
              <Button
                type="button"
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  void run(() => adminResetEmailTemplate(tpl.kind), "Couldn't reset the template.")
                }
              >
                Reset to default
              </Button>
            )}
            <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
              Close
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

export function EmailTemplatesAdmin() {
  const [templates, setTemplates] = useState<EmailTemplate[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openKind, setOpenKind] = useState<string | null>(null);

  useEffect(() => {
    adminListEmailTemplates()
      .then(setTemplates)
      .catch((err) => setError(errorMessage(err, "Couldn't load the email templates.")));
  }, []);

  const openTpl = templates?.find((t) => t.kind === openKind) ?? null;

  return (
    <Card eyebrow="System" title="Automated emails">
      <p style={{ color: "var(--l360-bgrey)", marginBottom: 16 }}>
        The wording of every email the system sends on its own. Tap one to edit its subject
        and body.
      </p>
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {templates === null && !error && <p className="l360-empty">Loading…</p>}
      {templates?.map((tpl) => (
        <div key={tpl.kind} style={{ borderTop: "1px solid var(--l360-sand)" }}>
          <button
            type="button"
            className="l360-link-btn"
            onClick={() => setOpenKind(tpl.kind)}
            style={{
              display: "flex",
              width: "100%",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
              padding: "12px 0",
              textAlign: "left",
              textDecoration: "none",
            }}
          >
            <span style={{ fontWeight: 600 }}>{tpl.label}</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              {tpl.is_custom && <StatusBadge variant="info" label="Customised" />}
              <span aria-hidden="true">›</span>
            </span>
          </button>
        </div>
      ))}
      {openTpl && (
        <TemplateEditorModal
          key={openTpl.kind}
          tpl={openTpl}
          onSaved={(saved) =>
            setTemplates((prev) => prev?.map((t) => (t.kind === saved.kind ? saved : t)) ?? null)
          }
          onClose={() => setOpenKind(null)}
        />
      )}
    </Card>
  );
}
