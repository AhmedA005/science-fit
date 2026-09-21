"""
Alembic environment — connects migrations to our models and database.

Key responsibilities:
1. Set the DB URL from Config (keeps credentials out of alembic.ini)
2. Import all models so Alembic can diff them against the DB
3. Support both offline (SQL script generation) and online (live DB) modes
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Load our app config and models ───────────────────────────────────────────
# Import Config first so .env is loaded
from src.config import Config  # noqa: E402

# Import ALL models via the package __init__.py.
# This registers every table with Base.metadata so Alembic can see them.
import src.models  # noqa: F401, E402
from src.models.base import Base  # noqa: E402

# ── Alembic Config object ─────────────────────────────────────────────────────
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tell Alembic what our schema looks like (all 15 tables)
target_metadata = Base.metadata

# Override the DB URL with our sync URL (psycopg2) — never from alembic.ini
config.set_main_option("sqlalchemy.url", Config.SYNC_DATABASE_URL)


def run_migrations_offline() -> None:
    """
    Offline mode: generate a .sql file instead of touching the DB.
    Useful for reviewing what will run before applying it.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Online mode: connect to the live DB and apply migrations directly.
    This is what `alembic upgrade head` uses.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # no pooling in migration scripts
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
