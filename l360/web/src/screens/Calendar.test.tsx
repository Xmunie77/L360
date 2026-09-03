import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { Calendar } from "./Calendar";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    listRooms: vi.fn(),
    listEducators: vi.fn(),
    listClients: vi.fn(),
    listSessionTypes: vi.fn(),
    listBookings: vi.fn(),
    getNextAvailableRoom: vi.fn(),
  };
});

import { getNextAvailableRoom, listBookings, listClients, listEducators, listRooms, listSessionTypes } from "../api/client";

const mockListRooms = vi.mocked(listRooms);
const mockListEducators = vi.mocked(listEducators);
const mockListClients = vi.mocked(listClients);
const mockListSessionTypes = vi.mocked(listSessionTypes);
const mockListBookings = vi.mocked(listBookings);
const mockGetNextAvailableRoom = vi.mocked(getNextAvailableRoom);

describe("Calendar", () => {
  it("renders the date picker and one column per active room without crashing", async () => {
    mockListRooms.mockResolvedValue([
      { id: 1, name: "Room A", sort_order: 0, active: true },
      { id: 2, name: "Room B", sort_order: 1, active: true },
    ]);
    mockListEducators.mockResolvedValue([
      { id: 10, email: "m.vella@example.org", full_name: "M. Vella", role: "educator", level_id: 1, active: true },
    ]);
    mockListClients.mockResolvedValue([
      { id: 20, guardian_first_name: "Aġius", guardian_surname: "family", child_name: "AG-1" },
    ]);
    mockListSessionTypes.mockResolvedValue([
      { id: 30, name: "Consultant Office Session", category: "session", client_price_cents: 3500, tutor_payment_cents: 3000, requires_room: true, sort_order: 0, active: true },
    ]);
    mockListBookings.mockResolvedValue([
      {
        id: 100,
        room_id: 1,
        room_name: "Room A",
        educator_id: 10,
        educator_name: "M. Vella",
        client_id: 20,
        client_label: "Aġius family (AG-1)",
        series_id: null,
        service_type_id: 30,
        service_type_name: "Consultant Office Session",
        client_price_cents: 3500,
        tutor_payment_cents: 3000,
        start_utc: new Date().toISOString(),
        duration_minutes: 60,
        status: "confirmed",
        notes: null,
        created_by: 1,
        created_at: new Date().toISOString(),
        cancelled_at: null,
        invoiced: false,
        charge_waived: false,
        billing_state: "none" as const,
      },
    ]);
    mockGetNextAvailableRoom.mockResolvedValue({
      room_id: 2,
      room_name: "Room B (next available)",
      start_utc: new Date(Date.now() + 3600_000).toISOString(),
      reason: null,
    });

    render(<Calendar me={null} />);

    // Date picker defaulting to today.
    const dateInput = screen.getByLabelText("Day") as HTMLInputElement;
    expect(dateInput.type).toBe("date");
    expect(dateInput.value).not.toBe("");

    // One room-lane column heading per active room.
    await waitFor(() => {
      expect(screen.getByText("Room A")).toBeTruthy();
      expect(screen.getByText("Room B")).toBeTruthy();
    });

    // Next-available-room bar, above the scheduling grid.
    await waitFor(() => expect(screen.getByRole("button", { name: "Book" })).toBeTruthy());

    // The booking for today renders as a block in its room's column.
    await waitFor(() => {
      expect(screen.getByText("M. Vella")).toBeTruthy();
    });
  });

  it("explains when nothing is available because facility hours aren't set up", async () => {
    mockListRooms.mockResolvedValue([{ id: 1, name: "Room A", sort_order: 0, active: true }]);
    mockListEducators.mockResolvedValue([]);
    mockListClients.mockResolvedValue([]);
    mockListSessionTypes.mockResolvedValue([]);
    mockListBookings.mockResolvedValue([]);
    mockGetNextAvailableRoom.mockResolvedValue({
      room_id: null,
      room_name: null,
      start_utc: null,
      reason: "no_facility_hours",
    });

    render(<Calendar me={null} />);

    await waitFor(() => expect(screen.getByText(/Facility hours/)).toBeTruthy());
    expect(screen.queryByRole("button", { name: "Book" })).toBeNull();
  });
});
