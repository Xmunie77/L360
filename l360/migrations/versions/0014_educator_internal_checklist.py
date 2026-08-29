"""educator_onboarding_forms.internal: the admin-side section-15 internal
onboarding checklist + final approval block, as one JSON document.

Revision ID: 0014_educator_internal_checklist
Revises: 0013_educator_onboarding
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0014_educator_internal_checklist"
down_revision = "0013_educator_onboarding"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.add_column("educator_onboarding_forms", sa.Column("internal", sa.JSON(), nullable=True), schema=_SCHEMA)


def downgrade() -> None:
    with op.batch_alter_table("educator_onboarding_forms", schema=_SCHEMA) as batch_op:
        batch_op.drop_column("internal")
