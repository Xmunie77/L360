"""app_settings: key/value app configuration editable from the Admin area
(first use: SMTP email settings, so the founders configure sending in-app).

Revision ID: 0010_app_settings
Revises: 0009_onboarding
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0010_app_settings"
down_revision = "0009_onboarding"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("key", name="uq_app_setting_key"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("app_settings", schema=_SCHEMA)
