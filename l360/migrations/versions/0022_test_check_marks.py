"""test_check_marks — founder test-script progress, one row per
(tester, checklist item). TEMPORARY: drop together with the
/api/test-script routes and the Test script tab once pre-launch
testing wraps (Simon, 05/09/2026).

Revision ID: 0022_test_check_marks
Revises: 0021_user_hr_details
Create Date: 2026-09-05
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0022_test_check_marks"
down_revision = "0021_user_hr_details"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None
_USERS_FK = f"{L360_SCHEMA}.users.id" if IS_POSTGRES else "users.id"


def upgrade() -> None:
    op.create_table(
        "test_check_marks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(_USERS_FK), nullable=False),
        sa.Column("item_id", sa.String(20), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "item_id", name="uq_test_mark_user_item"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("test_check_marks", schema=_SCHEMA)
