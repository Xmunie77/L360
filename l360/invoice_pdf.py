"""Client invoice PDF — matches the Foundation's existing invoice layout
(the four samples in Drive L360/, e.g. "Invoice AmyGarziaNov25.pdf"):
INVOICE + reference top right, logo top left, foundation address/VAT/bank
block, Bill To (learner bold + ATTN payers), dark-header Item/Quantity/
Rate/Amount table, and Total / Amount Paid / Balance Due. One deliberate
addition over the samples: the educator's name appears on every line
(Simon, 30/08/2026).

Pure and DB-free: the API assembles an InvoicePdfData and this renders it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date

from fpdf import FPDF

from l360.config import (
    INVOICE_ADDRESS_LINES,
    INVOICE_BANK_LINES,
    INVOICE_CONTACT_LINES,
    INVOICE_FOUNDATION_NAME,
    INVOICE_VAT_LINE,
)

# app_settings keys for the letterhead, editable from Admin -> Invoicing.
# DB values override the config defaults, same pattern as the SMTP settings.
INVOICE_SETTING_KEYS = ("invoice_name", "invoice_address", "invoice_vat", "invoice_bank", "invoice_contact", "invoice_footer")

_DEFAULTS = {
    "invoice_name": INVOICE_FOUNDATION_NAME,
    "invoice_address": "\n".join(INVOICE_ADDRESS_LINES),
    "invoice_vat": INVOICE_VAT_LINE,
    "invoice_bank": "\n".join(INVOICE_BANK_LINES),
    "invoice_contact": "\n".join(INVOICE_CONTACT_LINES),
    "invoice_footer": "",
}


def letterhead() -> dict:
    # Effective letterhead: config defaults overridden per-key by any
    # app_settings rows. Never raises: a DB hiccup means defaults.
    values = dict(_DEFAULTS)
    try:
        from sqlalchemy import select

        from l360.db import SessionLocal
        from l360.models import AppSetting

        with SessionLocal() as db:
            for row in db.scalars(select(AppSetting).where(AppSetting.key.in_(INVOICE_SETTING_KEYS))):
                if row.value.strip():
                    values[row.key] = row.value
    except Exception:
        pass
    return values

_LOGO = os.path.join(os.path.dirname(__file__), "design", "learning360-mark-orange.png")

INK = (36, 33, 31)
GREY = (150, 145, 140)
HEADER_BG = (42, 47, 54)      # the samples' dark table header
DUE_BG = (241, 243, 245)      # pale grey Balance Due band


@dataclass
class InvoiceLinePdf:
    description: str
    quantity: int
    unit_price_cents: int
    amount_cents: int


@dataclass
class InvoicePdfData:
    number: str                      # e.g. L360-2026-0007, or "DRAFT"
    issue_date: date
    learner_name: str                # bold Bill To line
    attn: str                        # payers, e.g. "Mark and Tanya Garzia"
    bill_address: str | None
    lines: list[InvoiceLinePdf] = field(default_factory=list)
    total_cents: int = 0
    paid_cents: int = 0

    @property
    def balance_cents(self) -> int:
        return self.total_cents - self.paid_cents


def _eur(cents: int) -> str:
    return f"€{cents / 100:,.2f}"


def build_invoice_pdf(data: InvoicePdfData, head: dict | None = None) -> bytes:
    head = head or letterhead()
    pdf = FPDF(format="A4")
    # cp1252, not latin-1: the € sign (and the em dashes in line
    # descriptions) only exist in the former for core PDF fonts.
    pdf.core_fonts_encoding = "windows-1252"
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_text_color(*INK)

    # --- header: logo left, INVOICE + reference right -----------------------
    if os.path.exists(_LOGO):
        pdf.image(_LOGO, x=12, y=14, w=11)
    pdf.set_xy(25, 15)
    pdf.set_font("helvetica", "B", 13)
    pdf.cell(60, 5, "Learning")
    pdf.set_xy(25, 20)
    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(*GREY)
    pdf.cell(60, 5, "360°")
    pdf.set_text_color(*INK)

    pdf.set_xy(110, 12)
    pdf.set_font("helvetica", "", 28)
    pdf.cell(88, 12, "INVOICE", align="R")
    pdf.set_xy(110, 24)
    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(*GREY)
    pdf.cell(88, 6, data.number, align="R")
    pdf.set_text_color(*INK)

    # --- date + balance due band (right) ------------------------------------
    pdf.set_xy(110, 38)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(50, 6, "Date:", align="R")
    pdf.set_text_color(*INK)
    pdf.cell(38, 6, data.issue_date.strftime("%-d %b %Y"), align="R")
    pdf.set_xy(104, 46)
    pdf.set_fill_color(*DUE_BG)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(56, 9, "Balance Due:", align="R", fill=True)
    pdf.cell(38, 9, _eur(data.balance_cents), align="R", fill=True)

    # --- foundation block (left) --------------------------------------------
    y = 40
    pdf.set_xy(12, y)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(90, 5, head["invoice_name"])
    pdf.set_font("helvetica", "", 9.5)
    head_lines = []
    for key in ("invoice_address", "invoice_vat", "invoice_bank", "invoice_contact"):
        head_lines.extend(l.strip() for l in head[key].splitlines() if l.strip())
    for line in head_lines:
        y += 5
        pdf.set_xy(12, y)
        pdf.cell(95, 5, line)

    # --- Bill To -------------------------------------------------------------
    y += 11
    pdf.set_xy(12, y)
    pdf.set_font("helvetica", "", 9.5)
    pdf.set_text_color(*GREY)
    pdf.cell(90, 5, "Bill To:")
    pdf.set_text_color(*INK)
    y += 5
    pdf.set_xy(12, y)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(90, 5, data.learner_name)
    if data.attn:
        y += 5
        pdf.set_xy(12, y)
        pdf.set_font("helvetica", "", 9.5)
        pdf.cell(120, 5, f"ATTN: {data.attn}")
    if data.bill_address:
        for part in data.bill_address.splitlines():
            y += 5
            pdf.set_xy(12, y)
            pdf.set_font("helvetica", "", 9.5)
            pdf.cell(120, 5, part.strip())

    # --- items table ----------------------------------------------------------
    y = max(y + 12, 118)
    widths = (110, 22, 27, 27)
    pdf.set_xy(12, y)
    pdf.set_fill_color(*HEADER_BG)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "", 10)
    for w, label, align in zip(widths, ("Item", "Quantity", "Rate", "Amount"), ("L", "C", "R", "R")):
        pdf.cell(w, 8, label, align=align, fill=True)
    pdf.set_text_color(*INK)
    pdf.ln(11)

    for line in data.lines:
        pdf.set_x(12)
        pdf.set_font("helvetica", "B", 9.5)
        # multi_cell for long descriptions (service — date — educator)
        x, cy = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(widths[0], 5.5, line.description, align="L")
        row_h = max(pdf.get_y() - cy, 5.5)
        pdf.set_xy(x + widths[0], cy)
        pdf.set_font("helvetica", "", 9.5)
        pdf.cell(widths[1], 5.5, str(line.quantity), align="C")
        pdf.cell(widths[2], 5.5, _eur(line.unit_price_cents), align="R")
        pdf.cell(widths[3], 5.5, _eur(line.amount_cents), align="R")
        pdf.set_y(cy + row_h + 3)

    # --- totals ---------------------------------------------------------------
    # Same right-column geometry as the Date row and Balance Due band:
    # labels end at x=160, values right-aligned to the table edge at x=198.
    pdf.ln(8)
    for label, cents, grey in (("Total:", data.total_cents, True), ("Amount Paid:", data.paid_cents, True)):
        pdf.set_x(104)
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(*(GREY if grey else INK))
        pdf.cell(56, 7, label, align="R")
        pdf.set_text_color(*INK)
        pdf.cell(38, 7, _eur(cents), align="R")
        pdf.ln(7)
    pdf.set_x(104)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(56, 7, "Balance Due:", align="R")
    pdf.cell(38, 7, _eur(data.balance_cents), align="R")

    # --- optional footer note (e.g. payment terms) ---------------------------
    if head.get("invoice_footer", "").strip():
        pdf.ln(14)
        pdf.set_x(12)
        pdf.set_font("helvetica", "", 8.5)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(186, 4.5, head["invoice_footer"].strip())
        pdf.set_text_color(*INK)

    # --- footer ---------------------------------------------------------------
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-15)
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, f"PAGE {pdf.page_no()} OF {{nb}}")

    return bytes(pdf.output())
