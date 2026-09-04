import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Modal } from "./Modal";

describe("Modal", () => {
  it("announces itself as a dialog and closes on Escape", () => {
    const onClose = vi.fn();
    render(
      <Modal onClose={onClose}>
        <button type="button">Inside</button>
      </Modal>,
    );
    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("asks before discarding when dirty — Escape and backdrop alike", () => {
    const onClose = vi.fn();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { container } = render(
      <Modal onClose={onClose} dirty>
        <button type="button">Inside</button>
      </Modal>,
    );
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.click(container.querySelector(".l360-modal-backdrop")!);
    expect(confirmSpy).toHaveBeenCalledTimes(2);
    expect(onClose).not.toHaveBeenCalled();

    confirmSpy.mockReturnValue(true);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    confirmSpy.mockRestore();
  });

  it("focuses the first control on open", () => {
    render(
      <Modal onClose={() => {}}>
        <button type="button">First</button>
        <button type="button">Second</button>
      </Modal>,
    );
    expect(document.activeElement?.textContent).toBe("First");
  });

  it("clicking inside the card never closes", () => {
    const onClose = vi.fn();
    render(
      <Modal onClose={onClose}>
        <button type="button">Inside</button>
      </Modal>,
    );
    fireEvent.click(screen.getByText("Inside"));
    expect(onClose).not.toHaveBeenCalled();
  });
});
