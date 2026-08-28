import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Login } from "./Login";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, login: vi.fn(), forgotPassword: vi.fn() };
});

import { forgotPassword, login } from "../api/client";

const mockLogin = vi.mocked(login);
const mockForgotPassword = vi.mocked(forgotPassword);

describe("Login", () => {
  it("signs in on valid credentials", async () => {
    mockLogin.mockResolvedValue({ ok: true });
    const onSignedIn = vi.fn();
    render(<Login onSignedIn={onSignedIn} />);

    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: "admin@example.com" } });
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: "correcthorse" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(onSignedIn).toHaveBeenCalled());
    expect(mockLogin).toHaveBeenCalledWith("admin@example.com", "correcthorse");
  });

  it("switches to the forgot-password form and back", () => {
    render(<Login onSignedIn={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Forgot password?" }));
    expect(screen.getByRole("button", { name: "Send reset link" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Back to sign in" }));
    expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy();
  });

  it("shows a generic confirmation after requesting a reset link", async () => {
    mockForgotPassword.mockResolvedValue({ ok: true });
    render(<Login onSignedIn={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Forgot password?" }));
    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: "someone@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    await waitFor(() => expect(screen.getByRole("status")).toBeTruthy());
    expect(mockForgotPassword).toHaveBeenCalledWith("someone@example.com");
  });
});
