import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { App } from "./App";

// App now gates the shell behind /api/session — mock the client so these
// tests can drive both the signed-out and signed-in paths without a server.
vi.mock("./api/client", async () => {
  const actual = await vi.importActual<typeof import("./api/client")>("./api/client");
  return {
    ...actual,
    getSession: vi.fn(),
    getMe: vi.fn(),
    logout: vi.fn(),
    // The Calendar screen mounts as the default active view once signed
    // in — stub its reference-data calls so this test stays about the
    // shell/auth gate, not the calendar itself (see Calendar.test.tsx).
    listRooms: vi.fn().mockResolvedValue([]),
    listEducators: vi.fn().mockResolvedValue([]),
    listClients: vi.fn().mockResolvedValue([]),
    listBookings: vi.fn().mockResolvedValue([]),
  };
});

import { getMe, getSession } from "./api/client";

const mockGetSession = vi.mocked(getSession);
const mockGetMe = vi.mocked(getMe);

describe("App", () => {
  it("shows the login screen when there is no session", async () => {
    mockGetSession.mockResolvedValue({ authed: false });
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy());
  });

  it("shows the reset-password screen when the URL carries a reset token, regardless of session state", () => {
    window.history.pushState({}, "", "/?reset=some-token-value");
    render(<App />);
    expect(screen.getByRole("button", { name: "Set new password" })).toBeTruthy();
    window.history.pushState({}, "", "/");
  });

  it("renders the shell with the Calendar screen active by default once authed", async () => {
    mockGetSession.mockResolvedValue({ authed: true });
    mockGetMe.mockResolvedValue({ id: 1, email: "staff@example.org", full_name: "Staff Member", role: "admin", level_id: null });
    render(<App />);
    await waitFor(() => expect(screen.getAllByText("Calendar").length).toBeGreaterThan(0));
    expect(screen.getByAltText("Learning 360°")).toBeTruthy();
    expect(screen.getByText("Sessions")).toBeTruthy();
    expect(screen.getByText("Finance")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Profile" })).toBeTruthy();
  });
});
