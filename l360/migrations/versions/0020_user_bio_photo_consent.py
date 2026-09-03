"""users.bio / photo / photo_content_type / image_consent_at + source:
staff profile details for the Educators tab (Simon, 04/09/2026).

Photos and bios are used INSIDE the app (colleague-facing profiles), so
they carry a recorded consent — image use is one of the few staff-data
purposes where consent genuinely is the right lawful basis (unlike
contract/payroll/safeguarding data, which isn't consent-based).
Sensitive HR material — police conducts, ID numbers, home addresses —
deliberately stays in Drive, not here.

Revision ID: 0020_user_bio_photo_consent
Revises: 0019_booking_outcome_reason
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0020_user_bio_photo_consent"
down_revision = "0019_booking_outcome_reason"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True), schema=_SCHEMA)
    op.add_column("users", sa.Column("photo", sa.LargeBinary(), nullable=True), schema=_SCHEMA)
    op.add_column("users", sa.Column("photo_content_type", sa.String(100), nullable=True), schema=_SCHEMA)
    op.add_column("users", sa.Column("image_consent_at", sa.DateTime(timezone=True), nullable=True), schema=_SCHEMA)
    op.add_column("users", sa.Column("image_consent_source", sa.String(40), nullable=True), schema=_SCHEMA)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=_SCHEMA) as batch_op:
        batch_op.drop_column("image_consent_source")
        batch_op.drop_column("image_consent_at")
        batch_op.drop_column("photo_content_type")
        batch_op.drop_column("photo")
        batch_op.drop_column("bio")
