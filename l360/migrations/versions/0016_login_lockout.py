"""users.failed_logins / locked_until: login throttling (P0-1 of the
31/08/2026 engineering review) — 5 consecutive failures lock the account
for 15 minutes.

Revision ID: 0016_login_lockout
Revises: 0015_payment_received_by
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0016_login_lockout"
down_revision = "0015_payment_received_by"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.add_column("users", sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"), schema=_SCHEMA)
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True), schema=_SCHEMA)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=_SCHEMA) as batch_op:
        batch_op.drop_column("failed_logins")
        batch_op.drop_column("locked_until")
