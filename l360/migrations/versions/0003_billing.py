"""billing: invoices, invoice lines, payments, bank txns

Revision ID: 0003_billing
Revises: 0002_notification_logs
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0003_billing"
down_revision = "0002_notification_logs"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def _fk(table: str) -> str:
    return f"{L360_SCHEMA}.{table}.id" if IS_POSTGRES else f"{table}.id"


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey(_fk("clients")), nullable=False),
        sa.Column("number", sa.String(length=40), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("total_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey(_fk("users")), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("number", name="uq_invoice_number"),
        schema=_SCHEMA,
    )

    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey(_fk("invoices")), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey(_fk("bookings")), nullable=True),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        schema=_SCHEMA,
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey(_fk("invoices")), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("external_ref", sa.String(length=120), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("match_status", sa.String(length=10), nullable=False, server_default="manual"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey(_fk("users")), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    op.create_table(
        "bank_txns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("txn_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("reference", sa.String(length=300), nullable=True),
        sa.Column("counterparty", sa.String(length=300), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey(_fk("payments")), nullable=True),
        sa.UniqueConstraint("external_id", name="uq_bank_txn_external_id"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("bank_txns", schema=_SCHEMA)
    op.drop_table("payments", schema=_SCHEMA)
    op.drop_table("invoice_lines", schema=_SCHEMA)
    op.drop_table("invoices", schema=_SCHEMA)
