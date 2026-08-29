"""educator_onboarding_forms: tokenised educator onboarding questionnaire
(staff-side sibling of onboarding_forms) — answers stored as one JSON
document, signed declaration as first-class columns.

Revision ID: 0013_educator_onboarding
Revises: 0012_booking_price_snapshot
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0013_educator_onboarding"
down_revision = "0012_booking_price_snapshot"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.create_table(
        "educator_onboarding_forms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(f"{L360_SCHEMA}.users.id" if IS_POSTGRES else "users.id"),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answers", sa.JSON(), nullable=True),
        sa.Column("signature_name", sa.String(length=200), nullable=True),
        sa.Column("signed_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token", name="uq_educator_onboarding_token"),
        sa.UniqueConstraint("user_id", name="uq_educator_onboarding_user"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("educator_onboarding_forms", schema=_SCHEMA)
