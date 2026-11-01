"""Alembic runs this. The database address comes from app.config, not alembic.ini."""
from logging.config import fileConfig

from alembic import context

from app import config as app_config
from app import models  # noqa: F401  -- registers the tables on Base.metadata
from app.db import Base, make_engine, startup_lock

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
DATABASE_URL = config.get_main_option("sqlalchemy.url") or app_config.DATABASE_URL
# SQLite can't ALTER most columns in place; batch mode rebuilds the table instead.
RENDER_AS_BATCH = DATABASE_URL.startswith("sqlite")


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"}, render_as_batch=RENDER_AS_BATCH,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(DATABASE_URL)
    with engine.connect() as connection:
        if RENDER_AS_BATCH:
            # Batch mode drops and rebuilds tables. With foreign keys on, dropping
            # the old system table would cascade-delete every row that points at it.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        with startup_lock(connection):
            context.configure(
                connection=connection, target_metadata=target_metadata,
                render_as_batch=RENDER_AS_BATCH,
            )
            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
