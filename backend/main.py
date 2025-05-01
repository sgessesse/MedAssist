import sys
import os
import logging # Import logging
import logging.config # Import logging config

# --- Basic Logging Configuration --- #
# Configure logging early, before other modules might implicitly configure it.
# This setup sends INFO level logs and above to the console.
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False, # Keep existing loggers (like uvicorn's)
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout", # Default is stderr, stdout might be preferable for app logs
        },
    },
    "loggers": {
        "": { # Root logger
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "level": "INFO", # Uvicorn error logs
            "handlers": ["console"],
            "propagate": False,
        },
        "uvicorn.access": {
            "level": "INFO", # Uvicorn access logs
            "handlers": ["console"],
            "propagate": False,
        },
        "fastapi": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "sqlalchemy.engine": {
            "level": "WARNING", # Set to INFO to see SQL queries
            "handlers": ["console"],
            "propagate": False,
        },
        "apscheduler": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "backend": { # Catch-all for your application's modules
            "level": "INFO", # Set back to INFO
            "handlers": ["console"],
            "propagate": False,
        },
        "backend.core.scheduler": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
# ----------------------------------- #

# Add project root to sys.path to allow imports from backend
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import API routers
from backend.api.endpoints import chat, schedule, reminder
from backend.core.config import settings # Restore import
from backend.core.scheduler import start_scheduler, stop_scheduler # Import scheduler functions
# from backend.core.config import settings # We'll use this later

app = FastAPI(
    title="MedAssist API",
    description="API for the MedAssist virtual medical assistant.",
    version="0.1.0",
)

# --- Middleware --- #

# Configure CORS (Cross-Origin Resource Sharing)
# Allows requests from your frontend (running on a different port/domain)
origins = [
    "http://localhost",        # Allow localhost for local dev
    "http://localhost:3000",   # Default Next.js dev port
    "http://127.0.0.1:3000",
    # Add your frontend deployment URL here later
    # e.g., "https://your-frontend-app.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, etc.)
    allow_headers=["*"],  # Allows all headers
)

# --- API Routers --- #

# Include endpoint routers
# The prefix makes all routes in chat.py start with /api/v1/chat
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
# Restore other routers
app.include_router(schedule.router, prefix="/api/v1/schedule", tags=["Scheduling"])
app.include_router(reminder.router, prefix="/api/v1/reminders", tags=["Reminders"])

# --- Root Endpoint --- #

@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint to check if the API is running."""
    return {"message": "Welcome to the MedAssist API!"}

# --- Optional: Add lifespan events later for DB connection pools, etc. ---
# @app.on_event("startup")
# async def startup_event():
#     # Initialize database connections, etc.
#     pass

# @app.on_event("shutdown")
# async def shutdown_event():
#     # Close database connections, etc.
#     pass

# --- Lifespan Events for Scheduler --- #
@app.on_event("startup")
async def startup_event():
    """Starts the scheduler when the FastAPI app starts."""
    # --- Remove Debug Log --- #
    # try:
    #     logging.warning(f"--- [DEBUG main.py startup] Settings timezone before scheduler start: {settings.default_timezone}")
    #     logging.warning(f"--- [DEBUG main.py startup] All settings: {settings.dict()}")
    # except Exception as e:
    #     logging.error(f"--- [DEBUG main.py startup] Error accessing settings: {e}")
    # --- End Remove Debug Log --- #
    # Pass settings explicitly to the scheduler start function
    try:
        tz = settings.default_timezone
        interval = settings.reminder_check_interval_minutes
        start_scheduler(timezone=tz, interval_minutes=interval)
    except AttributeError as e:
        logging.error(f"CRITICAL: Failed to get settings needed for scheduler in startup: {e}")
    # start_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    """Stops the scheduler when the FastAPI app shuts down."""
    stop_scheduler()

# --- Run Command (for local development) --- #
# To run the API locally:
# uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 