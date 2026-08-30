"""payments.received_by_id: who physically received a cash payment
(custody trail — created_by only records who typed it in).

Revision ID: 0015_payment_received_by
Revises: 0014_educator_internal_checklist
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0015_payment_received_by"
down_revision = "0014_educator_internal_checklist"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("received_by_id", sa.Integer(), sa.ForeignKey(f"{L360_SCHEMA}.users.id" if IS_POSTGRES else "users.id"), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    with op.batch_alter_table("payments", schema=_SCHEMA) as batch_op:
        batch_op.drop_column("received_by_id")
