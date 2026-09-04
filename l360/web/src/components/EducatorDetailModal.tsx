import { useEffect, useRef, useState } from "react";
import { ConfirmButton } from "./ConfirmButton";
import { Modal } from "./Modal";
import { Button, Card, Input, StatusBadge, Textarea } from "../ui/ui";
import {
  ApiError,
  adminGetUserHr,
  adminSaveUserHr,
  adminUpdateUser,
  deleteUserPhoto,
  uploadUserPhoto,
  userPhotoUrl,
  type AdminUser,
  type UserHr,
} from "../api/client";

// Staff profile card — opened by tapping a name on the Educators tab.
// The top half is colleague-facing (photo, bio, role, level, contact);
// the photo/bio need a recorded consent, shown and revocable here.
// Below that, ADMINS ONLY see the HR details section (ID card, bank,
// emergency contact) — those fields exist only on the admin HR endpoints,
// so a non-admin session can't fetch them at all (Simon, 04/09/2026,
// revising the earlier keep-in-Drive stance).

export function EducatorAvatar({ user, size = 36 }: { user: AdminUser; size?: number }) {
  const initials = user.full_name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0] ?? "")
    .join("")
    .toUpperCase();
  const shared = {
    width: size,
    height: size,
    borderRadius: "50%",
    flexShrink: 0,
    objectFit: "cover" as const,
  };
  if (user.has_photo) {
    return <img src={userPhotoUrl(user.id)} alt="" style={shared} />;
  }
  return (
    <span
      aria-hidden="true"
      style={{
        ...shared,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--l360-sand, #EFEAE3)",
        color: "var(--l360-bgrey, #6E6660)",
        fontSize: Math.round(size / 2.6),
        fontWeight: 600,
      }}
    >
      {initials}
    </span>
  );
}

interface Props {
  user: AdminUser;
  levelName: string;
  canEdit: boolean;
  onClose: () => void;
  onChanged: () => void;
}

export function EducatorDetailModal({ user, levelName, canEdit, onClose, onChanged }: Props) {
  const [bio, setBio] = useState(user.bio ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function run(action: () => Promise<unknown>, failMsg: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : failMsg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal onClose={onClose} dirty={bio !== (user.bio ?? "")}>
        <Card eyebrow="Staffing" title={user.full_name}>
          <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 16 }}>
            <EducatorAvatar user={user} size={72} />
            <div>
              <p style={{ margin: 0, textTransform: "capitalize" }}>
                {user.role}
                {levelName ? ` · ${levelName}` : ""}
              </p>
              <p className="l360-field-hint" style={{ margin: "2px 0 0" }}>{user.email}</p>
              <p style={{ margin: "6px 0 0" }}>
                <StatusBadge
                  variant={user.active ? "success" : "pending"}
                  label={user.active ? "Active" : "Inactive"}
                />
              </p>
            </div>
          </div>

          {error && (
            <div className="l360-alert l360-alert-danger" role="alert">
              ⚠ {error}
            </div>
          )}

          {canEdit ? (
            <>
              <Textarea
                id={`edu-bio-${user.id}`}
                label="Bio"
                hint="A short paragraph — shown to colleagues on this page."
                value={bio}
                onChange={(e) => setBio(e.target.value)}
              />
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
                <Button
                  type="button"
                  onClick={() => void run(() => adminUpdateUser(user.id, { bio }), "Couldn't save the bio.")}
                  loading={busy}
                  loadingLabel="Saving…"
                >
                  Save bio
                </Button>
                <Button type="button" variant="secondary" disabled={busy} onClick={() => fileRef.current?.click()}>
                  {user.has_photo ? "Replace photo" : "Add photo"}
                </Button>
                {user.has_photo && (
                  <ConfirmButton
                    confirmLabel="Really remove?"
                    disabled={busy}
                    onConfirm={() => void run(() => deleteUserPhoto(user.id), "Couldn't remove the photo.")}
                  >
                    Remove photo
                  </ConfirmButton>
                )}
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  style={{ display: "none" }}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (file) void run(() => uploadUserPhoto(user.id, file), "Couldn't upload that photo.");
                  }}
                />
              </div>
            </>
          ) : (
            <p style={{ marginBottom: 16 }}>{user.bio || <span className="l360-field-hint">No bio yet.</span>}</p>
          )}

          <p className="l360-field-hint" style={{ marginBottom: 16 }}>
            {user.image_consent_at
              ? `Photo and bio used with consent recorded ${new Date(user.image_consent_at).toLocaleDateString("en-GB")}.`
              : "No image consent recorded yet — adding a photo records it."}
            {canEdit && user.image_consent_at && (
              <>
                {" "}
                <button
                  type="button"
                  className="l360-link-btn"
                  disabled={busy}
                  onClick={() => {
                    // Irreversible: consent record AND photo go together.
                    if (!window.confirm("Withdraw image consent and delete the photo?")) return;
                    void run(
                      () => adminUpdateUser(user.id, { image_consent: false }),
                      "Couldn't withdraw consent.",
                    );
                  }}
                >
                  Withdraw consent and delete photo
                </button>
              </>
            )}
          </p>

          {canEdit && <HrDetailsSection userId={user.id} />}

          <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
            Close
          </Button>
        </Card>
    </Modal>
  );
}

const HR_FIELDS: { key: keyof UserHr; label: string; hint?: string; type?: string }[] = [
  { key: "mobile", label: "Mobile" },
  { key: "address", label: "Home address" },
  { key: "id_card_number", label: "ID card number" },
  { key: "nationality", label: "Nationality" },
  { key: "date_of_birth", label: "Date of birth", type: "date" },
  { key: "iban", label: "IBAN" },
  { key: "bank_account_holder", label: "Bank account holder" },
  { key: "tax_vat_number", label: "Tax / VAT number" },
  { key: "social_security_number", label: "Social security number" },
  { key: "emergency_name", label: "Emergency contact" },
  { key: "emergency_phone", label: "Emergency phone" },
];

function HrDetailsSection({ userId }: { userId: number }) {
  const [hr, setHr] = useState<UserHr | null>(null);
  // What the server last confirmed — Cancel restores this, so discarded
  // edits can't sit in the read-only view looking saved.
  const [savedHr, setSavedHr] = useState<UserHr | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminGetUserHr(userId)
      .then((loaded) => {
        setHr(loaded);
        setSavedHr(loaded);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't load the HR details."));
  }, [userId]);

  async function save() {
    if (!hr) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await adminSaveUserHr(userId, hr);
      setHr(saved);
      setSavedHr(saved);
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't save the HR details.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ borderTop: "1px solid var(--l360-sand)", margin: "16px 0", paddingTop: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>HR details</h3>
        <StatusBadge variant="pending" label="Admins only" />
      </div>
      <p className="l360-field-hint" style={{ margin: "4px 0 12px" }}>
        Payment and statutory details — visible to admins only, never to colleagues.
      </p>
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {hr === null && !error && <p className="l360-empty">Loading…</p>}
      {hr && !editing && (
        <>
          <dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "4px 12px", margin: "0 0 12px" }}>
            {HR_FIELDS.map(({ key, label }) => (
              <div key={key} style={{ display: "contents" }}>
                <dt style={{ color: "var(--l360-bgrey)" }}>{label}</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{hr[key] || "—"}</dd>
              </div>
            ))}
          </dl>
          <Button type="button" variant="secondary" onClick={() => setEditing(true)}>
            Edit HR details
          </Button>
        </>
      )}
      {hr && editing && (
        <>
          {HR_FIELDS.map(({ key, label, hint, type }) => (
            <Input
              key={key}
              id={`hr-${key}-${userId}`}
              label={label}
              hint={hint}
              type={type}
              value={hr[key] ?? ""}
              onChange={(e) => setHr({ ...hr, [key]: e.target.value })}
            />
          ))}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button type="button" onClick={() => void save()} loading={busy} loadingLabel="Saving…">
              Save HR details
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy}
              onClick={() => {
                setHr(savedHr);
                setError(null);
                setEditing(false);
              }}
            >
              Cancel
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
