import os
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
from typing import Optional

# Construct the path to the .env file in the project root
# Assuming this config.py is in backend/core/
# project_root -> backend/
# project_root.parent -> MedAssist/
project_root = Path(__file__).resolve().parent.parent.parent
dotenv_path = project_root / '.env'

class Settings(BaseSettings):
    # --- LLM Configuration ---
    google_api_key: str = Field(..., validation_alias='GOOGLE_API_KEY')
    # Available models: gemini-1.5-flash-latest, gemini-1.5-pro-latest, gemini-1.0-pro
    # Flash is faster/cheaper, Pro is more capable.
    llm_model_name: str = "gemini-2.0-flash"
    embedding_model_name: str = "models/text-embedding-004"

    # --- Vector Store Configuration ---
    # Use Path for directory paths
    chroma_persist_dir: Path = project_root / "data" / "chroma_db"
    chroma_collection_name: str = "medical_knowledge"

    # --- Symptom Triage Configuration ---
    symptom_rules_path: Path = project_root / "data" / "symptom_rules.json"

    # --- Database Configuration ---
    # Already loaded by SQLAlchemy in database.py using getenv, but good to have here too
    postgres_db_url: Optional[str] = Field(None, validation_alias='POSTGRES_DB_URL')

    # --- Agent Configuration ---
    agent_temperature: float = 0.7 # Controls creativity vs. factuality
    agent_max_tokens: Optional[int] = 1024 # Max output length

    # --- Scheduler Configuration ---
    default_timezone: str = Field("UTC", validation_alias='DEFAULT_TIMEZONE')
    reminder_check_interval_minutes: int = Field(1, validation_alias='REMINDER_CHECK_INTERVAL_MINUTES')

    # --- Security (Example - not used yet) ---
    # jwt_secret_key: str = Field(..., validation_alias='JWT_SECRET_KEY')
    # algorithm: str = "HS256"
    # access_token_expire_minutes: int = 30

    class Config:
        # This allows BaseSettings to read from the .env file
        env_file = str(dotenv_path)
        env_file_encoding = 'utf-8'
        extra = 'ignore' # Ignore extra fields in .env

# Create a single instance of the settings to be used throughout the application
settings = Settings() 
# --- Add Debug Print ---
print(f"--- [DEBUG config.py] Settings loaded: timezone={getattr(settings, 'default_timezone', 'NOT FOUND')}")
# --- End Debug Print --- 