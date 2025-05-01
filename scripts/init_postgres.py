import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

# Add project root to Python path to allow importing from backend
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.models import Base # Import Base from models.py

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(project_root, '.env'))

def initialize_database():
    """Connects to the database specified in .env and creates tables."""
    database_url = os.getenv("POSTGRES_DB_URL")

    if not database_url:
        print("Error: POSTGRES_DB_URL environment variable not set.")
        print("Please create a .env file based on .env.example and set the variable.")
        sys.exit(1)

    print(f"Connecting to database: {database_url.split('@')[1]}...") # Mask password

    try:
        engine = create_engine(database_url)
        # Try to establish a connection to check if DB is reachable
        with engine.connect() as connection:
            print("Database connection successful.")

        print("Creating tables (if they don't exist)...")
        Base.metadata.create_all(bind=engine)
        print("Tables checked/created successfully.")

    except OperationalError as e:
        print(f"\nError connecting to database or creating tables:")
        print(f"  {e}")
        print("\nPlease check:")
        print("  - Is the PostgreSQL server running?")
        print("  - Is the POSTGRES_DB_URL in your .env file correct (user, password, host, port, dbname)?")
        print("  - Does the specified database exist?")
        print("  - Are networking/firewall rules allowing the connection?")
        sys.exit(1)
    except ImportError as e:
        print(f"Import Error: {e}")
        print("Have you installed all requirements from requirements.txt? (pip install -r requirements.txt)")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    initialize_database() 