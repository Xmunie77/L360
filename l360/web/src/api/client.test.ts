import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, cancelBooking, createBooking, getSession, listRooms, login } from "./client";

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 409 ? "Conflict" : "",
    json: async () => body,
  } as Response;
}

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends credentials: include on every call", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, [{ id: 1, name: "Room A", sort_order: 0, active: true }]));
    vi.stubGlobal("fetch", fetchMock);

    await listRooms();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.credentials).toBe("include");
  });

  it("sends credentials: include on POST calls too", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await login("staff@example.org", "hunter2");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/login");
    expect(init.credentials).toBe("include");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ email: "staff@example.org", password: "hunter2" });
  });

  it("resolves session/auth calls with the parsed body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { authed: true }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getSession()).resolves.toEqual({ authed: true });
  });

  it("throws an ApiError carrying the API's detail message on a non-2xx response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(409, { detail: "Room already booked for this time" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      createBooking({
        room_id: 1,
        educator_id: 2,
        client_id: 3,
        start_utc: "2026-09-01T09:00:00Z",
        duration_minutes: 60,
      }),
    ).rejects.toMatchObject(
      new ApiError(409, "Room already booked for this time"),
    );
  });

  it("surfaces the detail message from a 409 on cancel too", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(409, { detail: "Already cancelled" }));
    vi.stubGlobal("fetch", fetchMock);

    try {
      await cancelBooking(42);
      expect.unreachable("cancelBooking should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(409);
      expect((err as ApiError).detail).toBe("Already cancelled");
    }
  });
});
