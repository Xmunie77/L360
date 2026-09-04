import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CalendarFeedCard } from "./CalendarFeedCard";
import { UtilisationCard } from "./UtilisationCard";
import { Statements } from "./Statements";
import type { Me } from "../api/client";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    getMyCalendarToken: vi.fn(),
    createOrRotateCalendarToken: vi.fn(),
    revokeCalendarToken: vi.fn(),
    listEducators: vi.fn(),
    listClients: vi.fn(),
    getEducatorSummary: vi.fn(),
    getClientStatement: vi.fn(),
    getUtilisationReport: vi.fn(),
  };
});

import {
  createOrRotateCalendarToken,
  getEducatorSummary,
  getMyCalendarToken,
  getUtilisationReport,
  listClients,
  listEducators,
} from "../api/client";

const mockGetMyCalendarToken = vi.mocked(getMyCalendarToken);
const mockCreateOrRotateCalendarToken = vi.mocked(createOrRotateCalendarToken);
const mockListEducators = vi.mocked(listEducators);
const mockListClients = vi.mocked(listClients);
const mockGetEducatorSummary = vi.mocked(getEducatorSummary);
const mockGetUtilisationReport = vi.mocked(getUtilisationReport);

const EDUCATOR_ME: Me = { id: 7, email: "e@example.com", full_name: "E. Ducator", role: "educator", level_id: 1 };
const ADMIN_ME: Me = { id: 1, email: "a@example.com", full_name: "Ad Min", role: "admin", level_id: null };

describe("Statements", () => {
  it("renders the calendar subscribe card and lets a user get their feed link", async () => {
    mockGetMyCalendarToken.mockResolvedValue(null);
    mockCreateOrRotateCalendarToken.mockResolvedValue({ token: "abc123", feed_path: "/api/calendar/abc123.ics" });

    render(<CalendarFeedCard />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Get my calendar link" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Get my calendar link" }));
    await waitFor(() => expect(mockCreateOrRotateCalendarToken).toHaveBeenCalled());
  });

  it("an educator sees their own summary without an educator picker", async () => {
    mockGetMyCalendarToken.mockResolvedValue(null);
    mockGetEducatorSummary.mockResolvedValue({
      educator_id: 7, educator_name: "E. Ducator", period_start: "2026-08-01", period_end: "2026-08-28",
      sessions: [{ booking_id: 1, local_date: "2026-08-10", client_label: "Doe family", duration_minutes: 60, status: "completed", rate_cents: 1500 }],
      total_payable_cents: 1500,
    });

    render(<Statements me={EDUCATOR_ME} />);

    await waitFor(() => expect(mockGetEducatorSummary).toHaveBeenCalledWith(7, expect.any(String), expect.any(String)));
    expect(screen.queryByLabelText("Educator")).toBeNull(); // no picker for a non-admin
  });

  it("an admin sees the client statement section plus an educator picker", async () => {
    mockGetMyCalendarToken.mockResolvedValue(null);
    mockListEducators.mockResolvedValue([{ id: 7, email: "e@example.com", full_name: "E. Ducator", role: "educator", level_id: 1, active: true }]);
    mockListClients.mockResolvedValue([{ id: 3, guardian_first_name: "Doe", guardian_surname: "family", child_name: null }]);

    render(<Statements me={ADMIN_ME} />);

    // Finance lands on the Billing pill (first) for admins — the statement
    // sections live behind the Statements pill.
    await waitFor(() => expect(screen.getByRole("button", { name: "Run billing" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Statements" }));
    await waitFor(() => expect(screen.getByText("Learner statement")).toBeTruthy());
  });

  it("Finance carries the Invoices/Bank sub-nav for admins only", async () => {
    // Billing and Payments stopped being top-level tabs on 04/09/2026 — they
    // are pills inside Finance now. Educators must still see just their own
    // summary, with no pill bar at all.
    mockGetMyCalendarToken.mockResolvedValue(null);
    mockListEducators.mockResolvedValue([]);
    mockListClients.mockResolvedValue([]);

    const admin = render(<Statements me={ADMIN_ME} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Statements" })).toBeTruthy());
    expect(screen.getByRole("button", { name: "Billing" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Invoices" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Bank" })).toBeTruthy();
    admin.unmount();

    mockGetEducatorSummary.mockResolvedValue({
      educator_id: 7, educator_name: "E. Ducator", period_start: "2026-08-01", period_end: "2026-08-28",
      sessions: [], total_payable_cents: 0,
    });
    render(<Statements me={EDUCATOR_ME} />);
    await waitFor(() => expect(mockGetEducatorSummary).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Billing" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Invoices" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Bank" })).toBeNull();
  });

  it("the utilisation report renders on its own (now an Admin sub-tab)", async () => {
    mockGetUtilisationReport.mockResolvedValue([{ room_id: 1, room_name: "Room 1", session_count: 2, booked_minutes: 120 }]);

    render(<UtilisationCard />);

    await waitFor(() => expect(screen.getByText("Room utilisation")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("Room 1")).toBeTruthy());
  });
});
