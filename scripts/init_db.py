import sys
import os
import logging

# Add backend directory to Python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.append(backend_dir)

from app.database import engine, Base
from app import models # Import models to ensure they are registered with Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Attempting to create database tables...")
    try:
        # In a real application, consider using Alembic for migrations
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully (if they didn't exist).")
        # Log which tables were created or already exist
        logger.info(f"Registered tables: {Base.metadata.tables.keys()}")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 