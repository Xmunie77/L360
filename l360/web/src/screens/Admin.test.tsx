import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Admin } from "./Admin";

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
    adminListPriceList: vi.fn(),
    adminCreatePriceEntry: vi.fn(),
    adminListFacilityHours: vi.fn(),
    adminUpsertFacilityHours: vi.fn(),
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
  adminListFacilityHours,
  adminListRooms,
  adminListServiceTypes,
  adminUpsertFacilityHours,
} from "../api/client";

const mockAdminListRooms = vi.mocked(adminListRooms);
const mockAdminDeactivateRoom = vi.mocked(adminDeactivateRoom);
const mockAdminListClients = vi.mocked(adminListClients);
const mockAdminListFacilityHours = vi.mocked(adminListFacilityHours);
const mockAdminUpsertFacilityHours = vi.mocked(adminUpsertFacilityHours);
const mockAdminListServiceTypes = vi.mocked(adminListServiceTypes);

describe("Admin", () => {
  it("renders the tab bar and the rooms section without crashing", async () => {
    mockAdminListRooms.mockResolvedValue([{ id: 1, name: "Room A", sort_order: 0, active: true }]);

    render(<Admin />);

    expect(screen.getByRole("button", { name: "Educator levels" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Price list" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Facility hours" })).toBeTruthy();
    await waitFor(() => expect(screen.getByText("Room A")).toBeTruthy());
  });

  it("deactivating a room calls adminDeactivateRoom", async () => {
    mockAdminListRooms.mockResolvedValue([{ id: 1, name: "Room A", sort_order: 0, active: true }]);
    mockAdminDeactivateRoom.mockResolvedValue({ ok: true });

    render(<Admin />);
    await waitFor(() => expect(screen.getByText("Room A")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));

    await waitFor(() => expect(mockAdminDeactivateRoom).toHaveBeenCalledWith(1));
  });

  it("shows the clients tab with an add-client form", async () => {
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
      },
    ]);

    render(<Admin />);
    fireEvent.click(screen.getByRole("button", { name: "Learners" }));

    await waitFor(() => expect(screen.getByText("Aġius family")).toBeTruthy());
    expect(screen.getByRole("button", { name: "Add learner" })).toBeTruthy();
  });

  it("saving one day's facility hours doesn't clear another day's Saved confirmation", async () => {
    mockAdminListRooms.mockResolvedValue([]);
    mockAdminListFacilityHours.mockResolvedValue([
      { id: 1, weekday: 0, open_time: "09:00:00", close_time: "17:00:00" },
      { id: 2, weekday: 1, open_time: "09:00:00", close_time: "17:00:00" },
    ]);
    mockAdminUpsertFacilityHours.mockResolvedValue({ id: 1, weekday: 0, open_time: "09:00:00", close_time: "17:00:00" });

    render(<Admin />);
    fireEvent.click(screen.getByRole("button", { name: "Facility hours" }));
    await waitFor(() => expect(screen.getByLabelText("Monday open time")).toBeTruthy());

    const saveButtons = () => screen.getAllByRole("button", { name: /^Save(d)?$/ });

    fireEvent.click(saveButtons()[0]); // Monday
    await waitFor(() => expect(saveButtons()[0].textContent).toBe("Saved"));

    fireEvent.click(saveButtons()[1]); // Tuesday
    await waitFor(() => expect(saveButtons()[1].textContent).toBe("Saved"));
    // Monday must still read "Saved" — this is the regression the bug report caught.
    expect(saveButtons()[0].textContent).toBe("Saved");
  });

  it("splits service types into Sessions and Additional services tables", async () => {
    mockAdminListRooms.mockResolvedValue([]);
    mockAdminListServiceTypes.mockResolvedValue([
      { id: 1, name: "Onboarding Meeting", category: "session", client_price_cents: 3000, tutor_payment_cents: 2500, requires_room: true, sort_order: 0, active: true },
      { id: 2, name: "Flashcards A4", category: "additional_service", client_price_cents: 120, tutor_payment_cents: 50, requires_room: false, sort_order: 0, active: true },
    ]);

    render(<Admin />);
    fireEvent.click(screen.getByRole("button", { name: "Sessions & services" }));

    await waitFor(() => expect(screen.getByText("Onboarding Meeting")).toBeTruthy());
    expect(screen.getByText("Flashcards A4")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Sessions" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Additional services" })).toBeTruthy();
  });
});
