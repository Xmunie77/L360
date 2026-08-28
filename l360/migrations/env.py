"""Alembic environment for Learning 360°'s dedicated `l360` Postgres schema.

Mirrors kitchentable/migrations/env.py: the connection URL comes from
``l360.config.DATABASE_URL``; the app owns everything in the ``l360``
schema, so the version table is schema-qualified. Run gated via
workflow_dispatch, never on boot.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

from l360.config import IS_POSTGRES, L360_SCHEMA, DATABASE_URL
from l360.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

VERSION_TABLE = "l360_alembic_version"
VERSION_SCHEMA = L360_SCHEMA if IS_POSTGRES else None


def _include_name(name, type_, parent_names):
    if type_ == "schema":
        return name in (L360_SCHEMA, None)
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        version_table=VERSION_TABLE,
        version_table_schema=VERSION_SCHEMA,
        include_schemas=True,
        include_name=_include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool, future=True)
    with connectable.connect() as connection:
        if L360_SCHEMA and "postgresql" in DATABASE_URL:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{L360_SCHEMA}"'))
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            version_table=VERSION_TABLE,
            version_table_schema=VERSION_SCHEMA,
            include_schemas=True,
            include_name=_include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
