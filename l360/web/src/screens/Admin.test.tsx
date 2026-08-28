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
  };
});

import { adminDeactivateRoom, adminListClients, adminListRooms } from "../api/client";

const mockAdminListRooms = vi.mocked(adminListRooms);
const mockAdminDeactivateRoom = vi.mocked(adminDeactivateRoom);
const mockAdminListClients = vi.mocked(adminListClients);

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
        child_name: null,
        child_dob: null,
        observations: null,
        notes: null,
        active: true,
      },
    ]);

    render(<Admin />);
    fireEvent.click(screen.getByRole("button", { name: "Clients" }));

    await waitFor(() => expect(screen.getByText("Aġius family")).toBeTruthy());
    expect(screen.getByRole("button", { name: "Add client" })).toBeTruthy();
  });
});
