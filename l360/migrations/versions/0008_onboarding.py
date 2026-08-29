"""onboarding: the full client-onboarding questionnaire (mirrors the legacy
Google "Client Onboarding Form"). Adds the richer client fields (guardian ID,
second guardian, school, address, allergies) and the onboarding_forms table
that carries the tokenised form link, status, consent record and signatures.

Revision ID: 0008_onboarding
Revises: 0007_series_interval_weeks
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0008_onboarding"
down_revision = "0007_series_interval_weeks"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None

_CLIENT_COLUMNS = (
    sa.Column("guardian_id_number", sa.String(length=50), nullable=True),
    sa.Column("guardian2_name", sa.String(length=200), nullable=True),
    sa.Column("guardian2_id_number", sa.String(length=50), nullable=True),
    sa.Column("guardian2_email", sa.String(length=255), nullable=True),
    sa.Column("guardian2_phone", sa.String(length=50), nullable=True),
    sa.Column("school", sa.String(length=200), nullable=True),
    sa.Column("address", sa.Text(), nullable=True),
    sa.Column("has_allergies", sa.Boolean(), nullable=True),
    sa.Column("allergy_details", sa.Text(), nullable=True),
)


def upgrade() -> None:
    for col in _CLIENT_COLUMNS:
        op.add_column("clients", col, schema=_SCHEMA)

    op.create_table(
        "onboarding_forms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "client_id",
            sa.Integer(),
            sa.ForeignKey(f"{L360_SCHEMA}.clients.id" if IS_POSTGRES else "clients.id"),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fee_undertaking", sa.Boolean(), nullable=True),
        sa.Column("termination_60d_ack", sa.Boolean(), nullable=True),
        sa.Column("info_storage_consent", sa.Boolean(), nullable=True),
        sa.Column("marketing_opt_in", sa.Boolean(), nullable=True),
        sa.Column("epinephrine_ack", sa.Boolean(), nullable=True),
        sa.Column("accident_ack", sa.Boolean(), nullable=True),
        sa.Column("cancellation_policy_ack", sa.Boolean(), nullable=True),
        sa.Column("illness_policy_ack", sa.Boolean(), nullable=True),
        sa.Column("signature_guardian1", sa.String(length=200), nullable=True),
        sa.Column("signature_guardian2", sa.String(length=200), nullable=True),
        sa.Column("signed_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token", name="uq_onboarding_token"),
        sa.UniqueConstraint("client_id", name="uq_onboarding_client"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("onboarding_forms", schema=_SCHEMA)
    with op.batch_alter_table("clients", schema=_SCHEMA) as batch_op:
        for col in _CLIENT_COLUMNS:
            batch_op.drop_column(col.name)
