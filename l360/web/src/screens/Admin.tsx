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

// `hint` renders as the pill's hover tooltip (native title attribute).
const TABS: { key: TabKey; label: string; hint: string }[] = [
  { key: "rooms", label: "Rooms", hint: "The bookable rooms and the order they appear in" },
  { key: "levels", label: "Educator levels", hint: "Educator grades — each tutor is assigned one; prices per level live under Sessions & services" },
  { key: "users", label: "Users", hint: "Staff accounts — educators and admins, logins, onboarding forms, vetting checklist and contracts" },
  { key: "clients", label: "Learners", hint: "Add learners, see onboarding status, resend forms, deactivate records" },
  { key: "service-types", label: "Sessions & services", hint: "Session types and the price list — what each session bills the family and pays the tutor" },
  { key: "hours", label: "Facility hours", hint: "Weekly opening hours — bookings must fall inside these" },
  { key: "closures", label: "Closures", hint: "One-off closed dates (public holidays etc.) — whole centre or a single room" },
  { key: "reports", label: "Reports", hint: "Room utilisation — how busy each room is over time" },
  { key: "email", label: "Email", hint: "Settings for the system's outgoing email, plus a test-email button" },
  { key: "invoicing", label: "Invoicing", hint: "Invoice letterhead, bank details and footer, with a sample PDF preview" },
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
              title={t.hint}
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
