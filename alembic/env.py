from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Reuse the application's database URL so Alembic migrates the same database
# the FastAPI app talks to.
config.set_main_option("sqlalchemy.url", settings.database_url)
# This project uses handwritten migrations, so we do not expose SQLAlchemy model
# metadata for Alembic autogeneration.
target_metadata = None


def run_migrations_offline() -> None:
    # Offline mode emits SQL from the migration scripts without opening a live DB
    # connection. Useful for environments where you want SQL output only.
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Online mode is the normal path for `alembic upgrade head`: create an engine,
    # connect to Postgres, and execute migration operations directly.
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool
    )

    with connectable.connect() as connection:
        # Bind Alembic's migration context to the open SQLAlchemy connection.
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
