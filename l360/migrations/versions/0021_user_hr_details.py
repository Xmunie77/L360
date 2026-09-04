"""users HR detail columns — mobile/address/ID card/nationality/DOB, bank
(IBAN + holder), tax + social security numbers, emergency contact.

Admin-only fields (Simon, 04/09/2026, revising the earlier keep-in-Drive
stance): needed so paying educators and statutory paperwork has one source.
Never exposed outside the require_admin HR endpoints. Names mirror the
educator onboarding form's §2 + §11 so a submitted form can fill them.

Revision ID: 0021_user_hr_details
Revises: 0020_user_bio_photo_consent
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0021_user_hr_details"
down_revision = "0020_user_bio_photo_consent"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None

_COLUMNS = [
    sa.Column("mobile", sa.String(50), nullable=True),
    sa.Column("address", sa.String(500), nullable=True),
    sa.Column("id_card_number", sa.String(50), nullable=True),
    sa.Column("nationality", sa.String(100), nullable=True),
    sa.Column("date_of_birth", sa.Date(), nullable=True),
    sa.Column("iban", sa.String(50), nullable=True),
    sa.Column("bank_account_holder", sa.String(200), nullable=True),
    sa.Column("tax_vat_number", sa.String(100), nullable=True),
    sa.Column("social_security_number", sa.String(100), nullable=True),
    sa.Column("emergency_name", sa.String(200), nullable=True),
    sa.Column("emergency_phone", sa.String(50), nullable=True),
]


def upgrade() -> None:
    for col in _COLUMNS:
        op.add_column("users", col, schema=_SCHEMA)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=_SCHEMA) as batch_op:
        for col in reversed(_COLUMNS):
            batch_op.drop_column(col.name)
