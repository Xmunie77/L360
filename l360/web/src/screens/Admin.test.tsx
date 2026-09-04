import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Admin } from "./Admin";
import { ClientsAdmin } from "./admin/ClientsAdmin";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    adminListRooms: vi.fn(),
    adminCreateRoom: vi.fn(),
    adminUpdateRoom: vi.fn(),
    adminDeactivateRoom: vi.fn(),
    adminListEducatorLevels: vi.fn(),
    adminCreateEducatorLevel: vi.fn(),
    adminUpdateEducatorLevel: vi.fn(),
    adminListUsers: vi.fn(),
    adminCreateUser: vi.fn(),
    adminUpdateUser: vi.fn(),
    adminDeactivateUser: vi.fn(),
    adminListFacilityHours: vi.fn(),
    adminUpsertFacilityHours: vi.fn(),
    adminDeleteFacilityHours: vi.fn(),
    adminListClosures: vi.fn(),
    adminCreateClosure: vi.fn(),
    adminDeleteClosure: vi.fn(),
    adminListClients: vi.fn(),
    adminCreateClient: vi.fn(),
    adminUpdateClient: vi.fn(),
    adminListServiceTypes: vi.fn(),
    adminCreateServiceType: vi.fn(),
    adminUpdateServiceType: vi.fn(),
    adminDeactivateServiceType: vi.fn(),
  };
});

import {
  adminDeactivateRoom,
  adminListClients,
  adminListRooms,
  adminListServiceTypes,
} from "../api/client";

const mockAdminListRooms = vi.mocked(adminListRooms);
const mockAdminDeactivateRoom = vi.mocked(adminDeactivateRoom);
const mockAdminListClients = vi.mocked(adminListClients);
const mockAdminListServiceTypes = vi.mocked(adminListServiceTypes);

describe("Admin", () => {
  it("renders the tab bar and the rooms section without crashing", async () => {
    mockAdminListRooms.mockResolvedValue([{ id: 1, name: "Room A", sort_order: 0, active: true }]);

    render(<Admin />);

    expect(screen.getByRole("button", { name: "Educator levels" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Services Price List" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Invoice template" })).toBeTruthy();
    // Facility hours and Closures stopped gating bookings on 04/09/2026 —
    // educators run sessions whenever they like, so both screens are gone.
    expect(screen.queryByRole("button", { name: "Facility hours" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Closures" })).toBeNull();
    await waitFor(() => expect(screen.getByText("Room A")).toBeTruthy());
  });

  it("deactivating a room calls adminDeactivateRoom", async () => {
    mockAdminListRooms.mockResolvedValue([{ id: 1, name: "Room A", sort_order: 0, active: true }]);
    mockAdminDeactivateRoom.mockResolvedValue({ ok: true });

    render(<Admin />);
    await waitFor(() => expect(screen.getByText("Room A")).toBeTruthy());

    // Deactivate is now a two-step guard: first click arms, second confirms
    // (with a short double-tap grace period in between).
    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));
    expect(mockAdminDeactivateRoom).not.toHaveBeenCalled();
    await new Promise((r) => setTimeout(r, 400));
    fireEvent.click(screen.getByRole("button", { name: "Really deactivate?" }));

    await waitFor(() => expect(mockAdminDeactivateRoom).toHaveBeenCalledWith(1));
  });

  it("Learners screen (now a top-level tab, not under Admin) lists clients with an add form", async () => {
    mockAdminListRooms.mockResolvedValue([]);
    mockAdminListClients.mockResolvedValue([
      {
        id: 1,
        guardian_first_name: "Aġius",
        guardian_surname: "family",
        email: "agius@example.com",
        phone: null,
        guardian_id_number: null,
        guardian2_name: null,
        guardian2_id_number: null,
        guardian2_email: null,
        guardian2_phone: null,
        child_name: null,
        child_dob: null,
        school: null,
        address: null,
        has_allergies: null,
        allergy_details: null,
        observations: null,
        notes: null,
        active: true,
        onboarding_status: null,
        educators: ["M. Vella"],
      },
    ]);

    render(<ClientsAdmin />);

    await waitFor(() => expect(screen.getByText("Aġius family")).toBeTruthy());
    expect(screen.getByRole("button", { name: "Add learner" })).toBeTruthy();
    // And the Admin shell no longer offers a Learners pill.
    render(<Admin />);
    expect(screen.queryByRole("button", { name: "Learners" })).toBeNull();
  });

  it("splits service types into Sessions and Additional services tables", async () => {
    mockAdminListRooms.mockResolvedValue([]);
    mockAdminListServiceTypes.mockResolvedValue([
      { id: 1, name: "Onboarding Meeting", category: "session", client_price_cents: 3000, tutor_payment_cents: 2500, requires_room: true, sort_order: 0, active: true },
      { id: 2, name: "Flashcards A4", category: "additional_service", client_price_cents: 120, tutor_payment_cents: 50, requires_room: false, sort_order: 0, active: true },
    ]);

    render(<Admin />);
    fireEvent.click(screen.getByRole("button", { name: "Services Price List" }));

    await waitFor(() => expect(screen.getByText("Onboarding Meeting")).toBeTruthy());
    expect(screen.getByText("Flashcards A4")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Sessions" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Additional services" })).toBeTruthy();
  });
});
