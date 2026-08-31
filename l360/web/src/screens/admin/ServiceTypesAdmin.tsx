import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Input, Money, Select, StatusBadge } from "../../ui/ui";
import {
  adminCreateServiceType,
  adminDeactivateServiceType,
  adminListServiceTypes,
  adminUpdateServiceType,
  type ServiceType,
  type ServiceTypeCategory,
} from "../../api/client";
import { errorMessage } from "./shared";

// --- service types (named sessions/additional services) --------------------

const CATEGORY_OPTIONS: { value: ServiceTypeCategory; label: string }[] = [
  { value: "session", label: "Session" },
  { value: "additional_service", label: "Additional service" },
];

interface ServiceTypeDraft {
  name: string;
  client_price: string;
  tutor_payment: string;
  requires_room: boolean;
}

export function ServiceTypesAdmin() {
  const [serviceTypes, setServiceTypes] = useState<ServiceType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<ServiceTypeDraft>({
    name: "", client_price: "", tutor_payment: "", requires_room: true,
  });

  const [name, setName] = useState("");
  const [category, setCategory] = useState<ServiceTypeCategory>("session");
  const [clientPrice, setClientPrice] = useState("");
  const [tutorPayment, setTutorPayment] = useState("");
  const [requiresRoom, setRequiresRoom] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setServiceTypes(await adminListServiceTypes());
    } catch (err) {
      setError(errorMessage(err, "Couldn't load sessions & services."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !clientPrice || !tutorPayment) {
      setFormError("Give it a name and both prices.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      await adminCreateServiceType({
        name: name.trim(),
        category,
        client_price_cents: Math.round(Number(clientPrice) * 100),
        tutor_payment_cents: Math.round(Number(tutorPayment) * 100),
        requires_room: category === "session" ? requiresRoom : false,
        sort_order: 0,
        active: true,
      });
      setName("");
      setClientPrice("");
      setTutorPayment("");
      setRequiresRoom(true);
      await refresh();
    } catch (err) {
      setFormError(errorMessage(err, "Couldn't add this."));
    } finally {
      setSubmitting(false);
    }
  }

  function startEdit(row: ServiceType) {
    setEditingId(row.id);
    setEditDraft({
      name: row.name,
      client_price: (row.client_price_cents / 100).toFixed(2),
      tutor_payment: (row.tutor_payment_cents / 100).toFixed(2),
      requires_room: row.requires_room,
    });
    setError(null);
  }

  async function saveEdit(row: ServiceType) {
    if (!editDraft.name.trim() || !editDraft.client_price || !editDraft.tutor_payment) {
      setError("Give it a name and both prices.");
      return;
    }
    setBusyId(row.id);
    try {
      await adminUpdateServiceType(row.id, {
        name: editDraft.name.trim(),
        category: row.category,
        client_price_cents: Math.round(Number(editDraft.client_price) * 100),
        tutor_payment_cents: Math.round(Number(editDraft.tutor_payment) * 100),
        requires_room: row.category === "session" ? editDraft.requires_room : false,
        sort_order: row.sort_order,
        active: row.active,
      });
      setEditingId(null);
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save this."));
    } finally {
      setBusyId(null);
    }
  }

  async function toggleActive(row: ServiceType) {
    setBusyId(row.id);
    try {
      if (row.active) {
        await adminDeactivateServiceType(row.id);
      } else {
        await adminUpdateServiceType(row.id, {
          name: row.name,
          category: row.category,
          client_price_cents: row.client_price_cents,
          tutor_payment_cents: row.tutor_payment_cents,
          requires_room: row.requires_room,
          sort_order: row.sort_order,
          active: true,
        });
      }
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't update this."));
    } finally {
      setBusyId(null);
    }
  }

  function renderTable(rows: ServiceType[], emptyLabel: string, showRoomColumn: boolean) {
    if (rows.length === 0) return <p className="l360-empty">{emptyLabel}</p>;
    return (
      <div style={{ overflowX: "auto", marginBottom: 20 }}>
        <table className="l360-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Learner price</th>
              <th>Tutor payment</th>
              {showRoomColumn && <th>Needs a room?</th>}
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) =>
              editingId === r.id ? (
                <tr key={r.id}>
                  <td>
                    <input
                      className="l360-input"
                      aria-label="Name"
                      value={editDraft.name}
                      onChange={(e) => setEditDraft((d) => ({ ...d, name: e.target.value }))}
                    />
                  </td>
                  <td>
                    <input
                      className="l360-input"
                      type="number"
                      step="0.01"
                      min="0"
                      aria-label="Learner price (€)"
                      value={editDraft.client_price}
                      onChange={(e) => setEditDraft((d) => ({ ...d, client_price: e.target.value }))}
                    />
                  </td>
                  <td>
                    <input
                      className="l360-input"
                      type="number"
                      step="0.01"
                      min="0"
                      aria-label="Tutor payment (€)"
                      value={editDraft.tutor_payment}
                      onChange={(e) => setEditDraft((d) => ({ ...d, tutor_payment: e.target.value }))}
                    />
                  </td>
                  {showRoomColumn && (
                    <td>
                      <input
                        type="checkbox"
                        aria-label="Needs a room?"
                        checked={editDraft.requires_room}
                        onChange={(e) => setEditDraft((d) => ({ ...d, requires_room: e.target.checked }))}
                      />
                    </td>
                  )}
                  <td>
                    <StatusBadge variant={r.active ? "success" : "pending"} label={r.active ? "Active" : "Inactive"} />
                  </td>
                  <td style={{ display: "flex", gap: 8 }}>
                    <Button type="button" onClick={() => saveEdit(r)} loading={busyId === r.id} loadingLabel="Saving…">
                      Save
                    </Button>
                    <Button type="button" variant="secondary" onClick={() => setEditingId(null)}>
                      Cancel
                    </Button>
                  </td>
                </tr>
              ) : (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td><Money cents={r.client_price_cents} /></td>
                  <td><Money cents={r.tutor_payment_cents} /></td>
                  {showRoomColumn && <td>{r.requires_room ? "Yes" : "No"}</td>}
                  <td>
                    <StatusBadge variant={r.active ? "success" : "pending"} label={r.active ? "Active" : "Inactive"} />
                  </td>
                  <td style={{ display: "flex", gap: 8 }}>
                    <Button type="button" variant="secondary" onClick={() => startEdit(r)}>
                      Edit
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => toggleActive(r)}
                      loading={busyId === r.id}
                      loadingLabel="Saving…"
                    >
                      {r.active ? "Deactivate" : "Reactivate"}
                    </Button>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
    );
  }

  const sessions = serviceTypes.filter((s) => s.category === "session");
  const additionalServices = serviceTypes.filter((s) => s.category === "additional_service");

  return (
    <Card eyebrow="Finance" title="Sessions & services">
      <p className="l360-field-hint" style={{ marginBottom: 16 }}>
        Named prices from the foundation's price list that don't fit the level+duration model above —
        meetings, programmes and group sessions, plus one-off additional services like flashcards.
      </p>
      {error && (
        <div className="l360-alert l360-alert-danger" role="alert">
          ⚠ {error}
        </div>
      )}
      {loading ? (
        <p className="l360-empty">Loading…</p>
      ) : (
        <>
          <h4 style={{ marginBottom: 12 }}>Sessions</h4>
          {renderTable(sessions, "No sessions configured yet.", true)}

          <h4 style={{ marginBottom: 12 }}>Additional services</h4>
          {renderTable(additionalServices, "No additional services configured yet.", false)}
        </>
      )}

      <h4 style={{ marginBottom: 12 }}>Add a session or service</h4>
      <form onSubmit={handleCreate} noValidate>
        {formError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {formError}
          </div>
        )}
        <Input id="new-service-type-name" label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
        <Select
          id="new-service-type-category"
          label="Category"
          required
          value={category}
          onChange={(e) => setCategory(e.target.value as ServiceTypeCategory)}
          options={CATEGORY_OPTIONS}
        />
        <Input
          id="new-service-type-client-price"
          label="Learner price (€)"
          type="number"
          step="0.01"
          min="0"
          required
          value={clientPrice}
          onChange={(e) => setClientPrice(e.target.value)}
        />
        <Input
          id="new-service-type-tutor-payment"
          label="Tutor payment (€)"
          type="number"
          step="0.01"
          min="0"
          required
          value={tutorPayment}
          onChange={(e) => setTutorPayment(e.target.value)}
        />
        {category === "session" && (
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <input
              type="checkbox"
              checked={requiresRoom}
              onChange={(e) => setRequiresRoom(e.target.checked)}
            />
            Needs a room (unlike home/school visits)
          </label>
        )}
        <Button type="submit" loading={submitting} loadingLabel="Adding…">
          Add
        </Button>
      </form>
    </Card>
  );
}
