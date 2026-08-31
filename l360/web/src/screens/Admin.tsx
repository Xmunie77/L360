import { useState } from "react";
import { Button, Card } from "../ui/ui";
import { ClientsAdmin } from "./admin/ClientsAdmin";
import { ClosuresAdmin } from "./admin/ClosuresAdmin";
import { EmailSettingsAdmin } from "./admin/EmailSettingsAdmin";
import { FacilityHoursAdmin } from "./admin/FacilityHoursAdmin";
import { InvoiceSettingsAdmin } from "./admin/InvoiceSettingsAdmin";
import { LevelsAdmin } from "./admin/LevelsAdmin";
import { RoomsAdmin } from "./admin/RoomsAdmin";
import { ServiceTypesAdmin } from "./admin/ServiceTypesAdmin";
import { UsersAdmin } from "./admin/UsersAdmin";
import { UtilisationCard } from "./UtilisationCard";

// Admin shell: tab bar only — each tab's component lives in ./admin/*
// (split 31/08/2026, P3 of the engineering review, so parallel sessions
// stop colliding in one 1,900-line file).

type TabKey = "rooms" | "levels" | "users" | "clients" | "service-types" | "hours" | "closures" | "reports" | "email" | "invoicing";

const TABS: { key: TabKey; label: string }[] = [
  { key: "rooms", label: "Rooms" },
  { key: "levels", label: "Educator levels" },
  { key: "users", label: "Users" },
  { key: "clients", label: "Learners" },
  { key: "service-types", label: "Sessions & services" },
  { key: "hours", label: "Facility hours" },
  { key: "closures", label: "Closures" },
  { key: "reports", label: "Reports" },
  { key: "email", label: "Email" },
  { key: "invoicing", label: "Invoicing" },
];

export function Admin() {
  const [tab, setTab] = useState<TabKey>("rooms");

  return (
    <>
      <Card eyebrow="System" title="Admin">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {TABS.map((t) => (
            <Button
              key={t.key}
              type="button"
              variant={tab === t.key ? "primary" : "secondary"}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </Button>
          ))}
        </div>
      </Card>

      {tab === "rooms" && <RoomsAdmin />}
      {tab === "levels" && <LevelsAdmin />}
      {tab === "users" && <UsersAdmin />}
      {tab === "clients" && <ClientsAdmin />}
      {tab === "service-types" && <ServiceTypesAdmin />}
      {tab === "hours" && <FacilityHoursAdmin />}
      {tab === "closures" && <ClosuresAdmin />}
      {tab === "reports" && <UtilisationCard />}
      {tab === "email" && <EmailSettingsAdmin />}
      {tab === "invoicing" && <InvoiceSettingsAdmin />}
    </>
  );
}
