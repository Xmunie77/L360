import { useEffect, useRef, type ReactNode } from "react";

// The one modal shell (04/09/2026 UI audit). Before this, eleven modals
// were hand-rolled backdrop divs: Escape did nothing, Tab walked out into
// the page behind, focus never returned to the trigger, screen readers got
// no dialog announcement, and a stray backdrop tap threw away a half-typed
// form. Every modal now renders through here.
//
// `dirty` guards the two accidental exits (Escape, backdrop tap) with a
// native confirm; an explicit Close/Cancel button inside the modal calls
// `onClose` directly and is NOT guarded — pressing Cancel is a decision.

interface ModalProps {
  onClose: () => void;
  /** When true, Escape/backdrop ask before discarding. */
  dirty?: boolean;
  children: ReactNode;
}

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Modal({ onClose, dirty = false, children }: ModalProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const card = cardRef.current;
    // Focus the first control so keyboard users start inside the dialog.
    card?.querySelector<HTMLElement>(FOCUSABLE)?.focus();

    function maybeClose() {
      if (!dirtyRef.current || window.confirm("Discard your unsaved changes?")) {
        onCloseRef.current();
      }
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        maybeClose();
        return;
      }
      if (e.key !== "Tab" || !card) return;
      // Keep Tab inside the dialog, wrapping at both ends.
      const focusables = [...card.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
        (el) => el.offsetParent !== null,
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !card.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      opener?.focus?.();
    };
  }, []);

  function onBackdropClick() {
    if (!dirtyRef.current || window.confirm("Discard your unsaved changes?")) {
      onCloseRef.current();
    }
  }

  return (
    <div className="l360-modal-backdrop" onClick={onBackdropClick}>
      <div
        ref={cardRef}
        className="l360-modal-card"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
