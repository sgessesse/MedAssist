import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import logging

# Add project root to sys.path to allow imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import settings from the centralized config
from backend.core.config import settings

# Use the value from settings
DATABASE_URL = settings.postgres_db_url

# Keep the check, but rely on settings having loaded the value
if not DATABASE_URL:
    logging.error("FATAL ERROR: POSTGRES_DB_URL not found in settings. Check .env file and config.py.")
    # sys.exit(1)

# Create SQLAlchemy engine
# `pool_pre_ping` checks connections for validity before checkout
# `connect_args` can be used for SSL or other specific driver options
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    # connect_args={"sslmode": "require"} # Example for required SSL
) if DATABASE_URL else None # Only create engine if URL is set

# Create sessionmaker
# autocommit=False and autoflush=False are standard settings for FastAPI
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
) if engine else None

# Base class for models (can be imported from models.py too,
# but often defined here or in a dedicated core models file)
# Re-importing from models.py to ensure consistency
from backend.models import Base

# Dependency function to get a DB session
def get_db():
    """FastAPI dependency that provides a SQLAlchemy session."""
    if SessionLocal is None:
        logging.error("Database session not configured. Check POSTGRES_DB_URL and config.py.")
        raise RuntimeError("Database session not configured.")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Optional: Function to create tables (if not using Alembic migrations)
# def init_db():
#     if engine:
#         logging.info("Initializing database tables...")
#         Base.metadata.create_all(bind=engine)
#         logging.info("Database tables initialized.")
#     else:
#          logging.error("Cannot initialize DB tables, engine not created.") 