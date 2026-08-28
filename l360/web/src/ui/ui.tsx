// Learning 360° design-system component library — plain React + CSS classes
// defined in theme.css, styled entirely from ../../design/tokens.css.
// No UI framework. Mirrors kitchentable/web's hand-rolled ui.tsx approach.
//
// Components implemented per DESIGN_SYSTEM.md §5:
//   Button, Input, Textarea, Select, Card, StatusBadge, Money.

import {
  forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes,
  type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes,
} from "react";

// --- Button ------------------------------------------------------------
// Pill, weight 600, min-height 44px. Primary/secondary/destructive variants,
// disabled and loading states. One primary button per screen (caller's job).

export type ButtonVariant = "primary" | "secondary" | "destructive";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  /** Present-participle label shown while loading, e.g. "Paying…". */
  loadingLabel?: string;
  block?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", loading = false, loadingLabel, block = false, className = "", children, disabled, ...rest },
  ref,
) {
  const classes = [
    "l360-btn",
    `l360-btn-${variant}`,
    block ? "l360-btn-block" : "",
    className,
  ].filter(Boolean).join(" ");

  return (
    <button
      ref={ref}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (loadingLabel ?? children) : children}
    </button>
  );
});

// --- Input / Textarea / Select ------------------------------------------
// Label always above the field (never placeholder-only). Hint below in
// --l360-mute. Error state: danger border + message tied by aria-describedby.

interface FieldWrapperProps {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: (describedBy: string | undefined) => ReactNode;
}

function FieldWrapper({ id, label, hint, error, required, children }: FieldWrapperProps) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className={`l360-field${error ? " l360-field-error" : ""}`}>
      <label className="l360-field-label" htmlFor={id}>
        {label}
        {required ? " *" : ""}
      </label>
      {children(describedBy)}
      {hint && !error && (
        <span className="l360-field-hint" id={hintId}>{hint}</span>
      )}
      {error && (
        <span className="l360-field-error-msg" id={errorId} role="alert">
          ⚠ {error}
        </span>
      )}
    </div>
  );
}

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  id: string;
  label: string;
  hint?: string;
  error?: string;
}

export function Input({ id, label, hint, error, required, className = "", ...rest }: InputProps) {
  return (
    <FieldWrapper id={id} label={label} hint={hint} error={error} required={required}>
      {(describedBy) => (
        <input
          id={id}
          className={`l360-input ${className}`.trim()}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          {...rest}
        />
      )}
    </FieldWrapper>
  );
}

export interface TextareaProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> {
  id: string;
  label: string;
  hint?: string;
  error?: string;
}

export function Textarea({ id, label, hint, error, required, className = "", ...rest }: TextareaProps) {
  return (
    <FieldWrapper id={id} label={label} hint={hint} error={error} required={required}>
      {(describedBy) => (
        <textarea
          id={id}
          className={`l360-textarea ${className}`.trim()}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          {...rest}
        />
      )}
    </FieldWrapper>
  );
}

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
}

export function Select({ id, label, hint, error, required, options, placeholder, className = "", ...rest }: SelectProps) {
  return (
    <FieldWrapper id={id} label={label} hint={hint} error={error} required={required}>
      {(describedBy) => (
        <select
          id={id}
          className={`l360-select ${className}`.trim()}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          {...rest}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      )}
    </FieldWrapper>
  );
}

// --- Card ----------------------------------------------------------------
// r-md, 1px lgrey border, 20px padding. Optional eyebrow + title + body.

export interface CardProps {
  eyebrow?: string;
  title?: string;
  children?: ReactNode;
  className?: string;
}

export function Card({ eyebrow, title, children, className = "" }: CardProps) {
  return (
    <div className={`l360-card ${className}`.trim()}>
      {eyebrow && <span className="l360-card-eyebrow">{eyebrow}</span>}
      {title && <h3 className="l360-card-title">{title}</h3>}
      {children && <div className="l360-card-body">{children}</div>}
    </div>
  );
}

// --- Status badge ----------------------------------------------------
// Always renders a text label — colour is never the only signal. A
// no-show/missed-session badge MUST use "pending" (neutral), never "danger".

export type StatusVariant = "success" | "danger" | "info" | "pending";

export interface StatusBadgeProps {
  variant: StatusVariant;
  label: string;
}

export function StatusBadge({ variant, label }: StatusBadgeProps) {
  return <span className={`l360-badge l360-badge-${variant}`}>{label}</span>;
}

// --- Money -----------------------------------------------------------
// Formats integer cents as "€1,234.56" in the monospace token, so digits
// align in tables. Never pass floats — cents avoids rounding drift.

const EUR_FORMATTER = new Intl.NumberFormat("en-MT", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatMoney(cents: number): string {
  return EUR_FORMATTER.format(cents / 100);
}

export interface MoneyProps {
  cents: number;
  className?: string;
}

export function Money({ cents, className = "" }: MoneyProps) {
  return <span className={`l360-mono ${className}`.trim()}>{formatMoney(cents)}</span>;
}

// --- Wordmark ----------------------------------------------------------
// Real PNGs aren't available yet (see ../../design/ASSETS.md) — render the
// wordmark as styled Work Sans text. Once learning360-logo-white.png lands
// in ../../design/, swap the returned JSX for a single <img> tag; callers
// (App.tsx) don't need to change.

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`l360-wordmark ${className}`.trim()}>
      Learning 360<span className="degree">°</span>
    </span>
  );
}
