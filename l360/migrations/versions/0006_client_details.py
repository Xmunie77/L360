"""client_details: split guardian name into first/surname for alphabetical
sorting, and add child name/date of birth/observations captured at
onboarding.

Revision ID: 0006_client_details
Revises: 0005_password_reset_tokens
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

from l360.config import IS_POSTGRES, L360_SCHEMA

revision = "0006_client_details"
down_revision = "0005_password_reset_tokens"
branch_labels = None
depends_on = None

_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def upgrade() -> None:
    op.add_column("clients", sa.Column("guardian_first_name", sa.String(length=100), nullable=True), schema=_SCHEMA)
    op.add_column("clients", sa.Column("guardian_surname", sa.String(length=100), nullable=True), schema=_SCHEMA)
    op.add_column("clients", sa.Column("child_name", sa.String(length=200), nullable=True), schema=_SCHEMA)
    op.add_column("clients", sa.Column("child_dob", sa.Date(), nullable=True), schema=_SCHEMA)
    op.add_column("clients", sa.Column("observations", sa.Text(), nullable=True), schema=_SCHEMA)

    clients = sa.table(
        "clients",
        sa.column("id", sa.Integer()),
        sa.column("guardian_name", sa.String()),
        sa.column("guardian_first_name", sa.String()),
        sa.column("guardian_surname", sa.String()),
        sa.column("child_reference", sa.String()),
        sa.column("child_name", sa.String()),
        schema=_SCHEMA,
    )
    conn = op.get_bind()
    # One-time backfill: best-effort split of the existing free-text
    # "guardian_name" into first name / surname on the last space, so
    # existing (currently only test) clients keep working after the
    # guardian_name column is dropped below.
    for row in conn.execute(sa.select(clients.c.id, clients.c.guardian_name, clients.c.child_reference)):
        name = (row.guardian_name or "").strip()
        if " " in name:
            first, surname = name.rsplit(" ", 1)
        else:
            first, surname = "", (name or "—")
        conn.execute(
            clients.update()
            .where(clients.c.id == row.id)
            .values(guardian_first_name=first, guardian_surname=surname, child_name=row.child_reference)
        )

    # batch_alter_table so this also works on SQLite (local dev), which
    # can't ALTER COLUMN / DROP COLUMN directly — Postgres (production)
    # runs the same statements it always would inside the batch.
    with op.batch_alter_table("clients", schema=_SCHEMA) as batch_op:
        batch_op.alter_column("guardian_first_name", existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column("guardian_surname", existing_type=sa.String(length=100), nullable=False)
        batch_op.drop_column("guardian_name")
        batch_op.drop_column("child_reference")


def downgrade() -> None:
    op.add_column("clients", sa.Column("guardian_name", sa.String(length=200), nullable=True), schema=_SCHEMA)
    op.add_column("clients", sa.Column("child_reference", sa.String(length=200), nullable=True), schema=_SCHEMA)

    clients = sa.table(
        "clients",
        sa.column("id", sa.Integer()),
        sa.column("guardian_name", sa.String()),
        sa.column("guardian_first_name", sa.String()),
        sa.column("guardian_surname", sa.String()),
        sa.column("child_reference", sa.String()),
        sa.column("child_name", sa.String()),
        schema=_SCHEMA,
    )
    conn = op.get_bind()
    for row in conn.execute(sa.select(clients.c.id, clients.c.guardian_first_name, clients.c.guardian_surname, clients.c.child_name)):
        full_name = f"{row.guardian_first_name} {row.guardian_surname}".strip()
        conn.execute(
            clients.update().where(clients.c.id == row.id).values(guardian_name=full_name, child_reference=row.child_name)
        )

    with op.batch_alter_table("clients", schema=_SCHEMA) as batch_op:
        batch_op.alter_column("guardian_name", existing_type=sa.String(length=200), nullable=False)
        batch_op.drop_column("guardian_first_name")
        batch_op.drop_column("guardian_surname")
        batch_op.drop_column("child_name")
        batch_op.drop_column("child_dob")
        batch_op.drop_column("observations")
