import { useEffect, useState, type FormEvent } from "react";
import { ConfirmButton } from "../../components/ConfirmButton";
import { Button, Card, Input, StatusBadge } from "../../ui/ui";
import {
  adminCreateEducatorLevel,
  adminListEducatorLevels,
  adminUpdateEducatorLevel,
  type EducatorLevel,
} from "../../api/client";
import { errorMessage } from "./shared";

// --- educator levels -------------------------------------------------------

export function LevelsAdmin() {
  const [levels, setLevels] = useState<EducatorLevel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setLevels(await adminListEducatorLevels());
    } catch (err) {
      setError(errorMessage(err, "Couldn't load educator levels."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setFormError("Give the level a name.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      await adminCreateEducatorLevel({ name: name.trim(), sort_order: Number(sortOrder) || 0, active: true });
      setName("");
      setSortOrder("0");
      await refresh();
    } catch (err) {
      setFormError(errorMessage(err, "Couldn't create the level."));
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleActive(level: EducatorLevel) {
    setBusyId(level.id);
    try {
      await adminUpdateEducatorLevel(level.id, {
        name: level.name,
        sort_order: level.sort_order,
        active: !level.active,
      });
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't update this level."));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card eyebrow="Staffing" title="Educator levels">
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : levels.length === 0 ? (
        <p className="l360-empty">No educator levels configured yet.</p>
      ) : (
        <div style={{ overflowX: "auto", marginBottom: 20 }}>
          <table className="l360-table">
            <thead>
              <tr>
                <th>Level</th>
                <th>Sort order</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {levels.map((l) => (
                <tr key={l.id}>
                  <td>{l.name}</td>
                  <td className="l360-mono">{l.sort_order}</td>
                  <td>
                    <StatusBadge variant={l.active ? "success" : "pending"} label={l.active ? "Active" : "Inactive"} />
                  </td>
                  <td>
                    {l.active ? (
                      <ConfirmButton
                        onConfirm={() => void toggleActive(l)}
                        confirmLabel="Really deactivate?"
                        loading={busyId === l.id}
                        loadingLabel="Saving…"
                      >
                        Deactivate
                      </ConfirmButton>
                    ) : (
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => toggleActive(l)}
                        loading={busyId === l.id}
                        loadingLabel="Saving…"
                      >
                        Reactivate
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h4 style={{ marginBottom: 12 }}>Add a level</h4>
      <form onSubmit={handleCreate} noValidate>
        {formError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {formError}
          </div>
        )}
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
          <Input id="new-level-name" label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
          <Input
            id="new-level-sort"
            label="Sort order"
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
          />
          <div style={{ marginBottom: 16 }}>
            <Button type="submit" loading={submitting} loadingLabel="Adding…">
              Add level
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}
