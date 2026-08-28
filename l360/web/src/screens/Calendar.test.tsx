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
    listBookings: vi.fn(),
  };
});

import { listBookings, listClients, listEducators, listRooms } from "../api/client";

const mockListRooms = vi.mocked(listRooms);
const mockListEducators = vi.mocked(listEducators);
const mockListClients = vi.mocked(listClients);
const mockListBookings = vi.mocked(listBookings);

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
      { id: 20, guardian_name: "Aġius family", child_reference: "AG-1" },
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
        start_utc: new Date().toISOString(),
        duration_minutes: 60,
        status: "confirmed",
        notes: null,
        created_by: 1,
        created_at: new Date().toISOString(),
        cancelled_at: null,
      },
    ]);

    render(<Calendar />);

    // Date picker defaulting to today.
    const dateInput = screen.getByLabelText("Day") as HTMLInputElement;
    expect(dateInput.type).toBe("date");
    expect(dateInput.value).not.toBe("");

    // One room-lane column heading per active room.
    await waitFor(() => {
      expect(screen.getByText("Room A")).toBeTruthy();
      expect(screen.getByText("Room B")).toBeTruthy();
    });

    // The booking for today renders as a block in its room's column.
    await waitFor(() => {
      expect(screen.getByText("M. Vella")).toBeTruthy();
    });
  });
});
