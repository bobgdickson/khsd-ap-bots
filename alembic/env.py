from logging.config import fileConfig
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure app package is importable
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import DATABASE_URL, engine
from app.models import Base, BotProcessLog, BotRun

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata

print("Tables found:", target_metadata.tables.keys())


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        name_lower = name.lower()
        return (
            name_lower.startswith("ai_bot")
            or name_lower.startswith("ap_bot")
        )
    if type_ == "column":
        table_name = (compare_to.table.name if compare_to is not None else object.table.name).lower()
        return (
            table_name.startswith("ai_bot")
            or table_name.startswith("ap_bot")
        )
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        version_table="alembic_version_ap_bot",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            version_table="alembic_version_ap_bot",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
