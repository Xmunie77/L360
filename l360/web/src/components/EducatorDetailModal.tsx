import { useRef, useState } from "react";
import { Button, Card, StatusBadge, Textarea } from "../ui/ui";
import {
  ApiError,
  adminUpdateUser,
  deleteUserPhoto,
  uploadUserPhoto,
  userPhotoUrl,
  type AdminUser,
} from "../api/client";

// Staff profile card — opened by tapping a name on the Educators tab.
// Deliberately holds only colleague-facing details (photo, bio, role,
// level, contact). Police conducts, ID numbers and home addresses stay in
// Drive, out of the app (04/09/2026 privacy review); the photo/bio need a
// recorded consent, which is shown and revocable here.

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
    <div className="l360-modal-backdrop" onClick={onClose}>
      <div className="l360-modal-card" onClick={(e) => e.stopPropagation()}>
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
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => void run(() => deleteUserPhoto(user.id), "Couldn't remove the photo.")}
                  >
                    Remove photo
                  </Button>
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
                  onClick={() =>
                    void run(
                      () => adminUpdateUser(user.id, { image_consent: false }),
                      "Couldn't withdraw consent.",
                    )
                  }
                >
                  Withdraw consent and delete photo
                </button>
              </>
            )}
          </p>

          <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
            Close
          </Button>
        </Card>
      </div>
    </div>
  );
}
