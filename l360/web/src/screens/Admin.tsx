import { useState } from "react";
import { Button, Card } from "../ui/ui";
import { EmailSettingsAdmin } from "./admin/EmailSettingsAdmin";
import { InvoiceSettingsAdmin } from "./admin/InvoiceSettingsAdmin";
import { LevelsAdmin } from "./admin/LevelsAdmin";
import { RoomsAdmin } from "./admin/RoomsAdmin";
import { ServiceTypesAdmin } from "./admin/ServiceTypesAdmin";
import { UtilisationCard } from "./UtilisationCard";

// Admin shell: tab bar only — each tab's component lives in ./admin/*
// (split 31/08/2026, P3 of the engineering review, so parallel sessions
// stop colliding in one 1,900-line file).

type TabKey = "rooms" | "levels" | "service-types" | "reports" | "email" | "invoicing";

// `hint` renders as the pill's hover tooltip (native title attribute).
const TABS: { key: TabKey; label: string; hint: string }[] = [
  { key: "rooms", label: "Rooms", hint: "The bookable rooms and the order they appear in" },
  { key: "levels", label: "Educator levels", hint: "Educator grades — each tutor is assigned one; prices per level live under Services Price List" },
  { key: "service-types", label: "Services Price List", hint: "Session types and additional services — what each bills the family and pays the tutor" },
  { key: "reports", label: "Reports", hint: "Room utilisation — how busy each room is over time" },
  { key: "email", label: "Email", hint: "Settings for the system's outgoing email, plus a test-email button" },
  { key: "invoicing", label: "Invoice template", hint: "Invoice letterhead, bank details and footer, with a sample PDF preview" },
];

export function Admin() {
  const [tab, setTab] = useState<TabKey>("rooms");

  return (
    <>
      <Card>
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
      {tab === "service-types" && <ServiceTypesAdmin />}
      {tab === "reports" && <UtilisationCard />}
      {tab === "email" && <EmailSettingsAdmin />}
      {tab === "invoicing" && <InvoiceSettingsAdmin />}
    </>
  );
}
