from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# --- Alembic configuration --- #
import os
import sys

# Add project root to sys.path to find backend models
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# Import Base from your models file
from backend.models import Base
# --------------------------- #

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# --- Connect Database URL from alembic.ini --- #
# Retrieve the database URL from the Alembic config object,
# which should have loaded it from alembic.ini (reading the env var)
# Ensure POSTGRES_DB_URL is set in your environment before running alembic commands
import os # Re-import os if needed
from dotenv import load_dotenv

# Load .env file relative to the project root
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

db_url = os.getenv("POSTGRES_DB_URL")
if not db_url:
    print("Error: POSTGRES_DB_URL not found in environment for Alembic env.py")
    # Set a placeholder or raise error if needed, but alembic might handle it
    # We set it in alembic.ini using ${POSTGRES_DB_URL}, so config should have it
    # db_url = "postgresql://user:pass@host/db" # Placeholder if needed

# Set the SQLAlchemy URL in the config object if not already set
# This ensures run_migrations_offline/online get the URL
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)
else:
    print("Warning: Could not set sqlalchemy.url dynamically in env.py, relying on alembic.ini")
# ------------------------------------------ #

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# --- Set Target Metadata --- #
target_metadata = Base.metadata
# ------------------------- #

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
