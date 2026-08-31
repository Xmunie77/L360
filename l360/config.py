"""Configuration + environment for the Learning 360° (l360) app.

Mirrors the kitchentable config pattern: a SQLite default for local dev and
tests, Postgres in production via DATABASE_URL, and a fail-loud guard so the
app refuses to boot on Postgres with dev-default secrets.
"""
from __future__ import annotations

import os

# --- Database ---------------------------------------------------------------
# Local/test default is a SQLite file; production sets DATABASE_URL to Postgres.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(os.path.dirname(__file__), "l360_dev.db"),
)
IS_POSTGRES = DATABASE_URL.startswith("postgres")

# Postgres schema this app owns (analogous to kitchentable's `kitchen` schema).
L360_SCHEMA = os.environ.get("L360_SCHEMA", "l360")

# --- Auth (per-user accounts, HMAC-signed session cookie) -------------------
_DEV_SESSION_SECRET = "dev-insecure-l360-session-secret-change-me"
SESSION_SECRET = os.environ.get("L360_SESSION_SECRET", _DEV_SESSION_SECRET)

SESSION_COOKIE_NAME = "l360_session"
# Session lifetime — 14 days by default.
SESSION_TTL_SECONDS = int(os.environ.get("L360_SESSION_TTL", str(60 * 60 * 24 * 14)))

# Secure cookie flag defaults on under Postgres (served over HTTPS),
# off for local http dev. Overridable for edge cases.
COOKIE_SECURE = os.environ.get(
    "COOKIE_SECURE", "true" if IS_POSTGRES else "false"
).lower() in ("1", "true", "yes")

# --- Business constants -----------------------------------------------------
# The foundation invoices in euro and is VAT-exempt; sessions run on Malta time.
CURRENCY = "EUR"
TIMEZONE = "Europe/Malta"
# Cancellations inside this window count as "cancelled_late" (still billable).
CANCELLATION_CUTOFF_HOURS = int(os.environ.get("L360_CANCELLATION_CUTOFF_HOURS", "24"))
INVOICE_NUMBER_PREFIX = os.environ.get("L360_INVOICE_NUMBER_PREFIX", "L360")
VAT_EXEMPT_NOTE = os.environ.get("L360_VAT_EXEMPT_NOTE", "Exempt from VAT")

# Used to build absolute links in emails (password reset). Defaults to the
# production URL; override for local dev if you need a working reset link
# against a non-default port.
PUBLIC_BASE_URL = os.environ.get("L360_PUBLIC_URL", "https://l360-os.fly.dev")

# --- Invoice PDF details (printed on every client invoice) ------------------
INVOICE_FOUNDATION_NAME = os.environ.get("L360_INVOICE_NAME", "Learning 360 Foundation")
INVOICE_ADDRESS_LINES = (
    "'Orange Grove' Block C, Triq L-Ghabex",
    "Swatar BKR 4280",
)
INVOICE_VAT_LINE = os.environ.get("L360_INVOICE_VAT", "VAT No: 2872 5014 VO/1863")
INVOICE_BANK_LINES = (
    "Bank: APS",
    "Account Number: 4448401001-1",
    "IBAN: MT75APSB77013000000044484010011",
)
INVOICE_CONTACT_LINES = ("info@learning360.org.mt", "7942 2001")

# --- Error monitoring (no-op until the Fly secret is set) -------------------
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")

# --- Email (defined now, unused until the notifications phase) --------------
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("L360_EMAIL_FROM", "")

# --- Revolut Business (defined now, unused until the reconciliation phase) --
REVOLUT_API_BASE = os.environ.get("REVOLUT_API_BASE", "https://b2b.revolut.com/api/1.0")
REVOLUT_API_TOKEN = os.environ.get("REVOLUT_API_TOKEN", "")


def assert_secure_config() -> None:
    """Refuse to boot on Postgres with insecure dev defaults."""
    if not IS_POSTGRES:
        return
    problems = []
    if SESSION_SECRET == _DEV_SESSION_SECRET:
        problems.append("L360_SESSION_SECRET is still the dev default")
    if problems:
        raise RuntimeError(
            "Refusing to start with insecure production config: "
            + "; ".join(problems)
        )
