import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "../ui/ui";

// Two-step guard for irreversible one-click actions (04/09/2026 UI audit:
// every Deactivate / Remove photo / Reset looked like Edit and fired
// instantly). First click arms the button — it turns destructive and asks
// its confirm question; a second, deliberate click runs the action. It
// disarms by itself after a few seconds, and ignores clicks in the first
// 350ms after arming so a double-tap can't confirm by accident.

interface ConfirmButtonProps {
  onConfirm: () => void;
  confirmLabel: string;
  children: ReactNode;
  /** Resting look; the armed state is always destructive. */
  variant?: "secondary" | "destructive";
  disabled?: boolean;
  loading?: boolean;
  loadingLabel?: string;
}

const DISARM_AFTER_MS = 5000;
const DOUBLE_TAP_GUARD_MS = 350;

export function ConfirmButton({
  onConfirm,
  confirmLabel,
  children,
  variant = "secondary",
  disabled,
  loading,
  loadingLabel,
}: ConfirmButtonProps) {
  const [armed, setArmed] = useState(false);
  const armedAt = useRef(0);

  useEffect(() => {
    if (!armed) return;
    const id = window.setTimeout(() => setArmed(false), DISARM_AFTER_MS);
    return () => window.clearTimeout(id);
  }, [armed]);

  function handleClick() {
    if (!armed) {
      armedAt.current = Date.now();
      setArmed(true);
      return;
    }
    if (Date.now() - armedAt.current < DOUBLE_TAP_GUARD_MS) return;
    setArmed(false);
    onConfirm();
  }

  return (
    <Button
      type="button"
      variant={armed ? "destructive" : variant}
      onClick={handleClick}
      onBlur={() => setArmed(false)}
      disabled={disabled}
      loading={loading}
      loadingLabel={loadingLabel}
    >
      {armed ? confirmLabel : children}
    </Button>
  );
}
