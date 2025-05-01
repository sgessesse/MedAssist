import logging
from datetime import datetime
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler # Use AsyncIO for FastAPI compatibility
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from typing import Optional
import pytz

from backend.database import SessionLocal, engine # Need engine for JobStore
from backend import crud, schemas
from backend.core.config import settings

# Configure logging for the scheduler
# Remove this - configuration is now done in main.py
# logging.basicConfig()
# logging.getLogger('apscheduler').setLevel(logging.INFO)

# Get a logger instance specific to this module
logger = logging.getLogger(__name__)

# --- Configure Job Store and Executor ---
# Using SQLAlchemyJobStore allows jobs to persist across restarts if needed,
# though for a simple demo, MemoryJobStore might suffice.
# Using the same engine as the main app.
jobstores = {
    'default': SQLAlchemyJobStore(engine=engine)
}
executors = {
    'default': ThreadPoolExecutor(10) # Adjust pool size as needed
}
job_defaults = {
    'coalesce': False, # Run missed jobs? Set True if needed.
    'max_instances': 3 # Max concurrent instances of the same job
}

# Define scheduler globally but initialize later
scheduler: Optional[AsyncIOScheduler] = None

# --- Reminder Job Function ---

async def check_and_send_reminders():
    """
    Periodically checks the database for reminders that are due and "sends" them.
    Currently, "sending" means logging to the console.
    Includes basic error handling for DB operations.
    """
    # Add log right at the beginning
    logger.info("Scheduler Job: Entered check_and_send_reminders function.")
    db: Session = SessionLocal()
    if not db:
        logger.error("Scheduler Job: Failed to get DB session.")
        return

    try:
        now = datetime.now(scheduler.timezone) # Use scheduler's timezone
        due_reminders = crud.get_due_reminders(db, now)

        if not due_reminders:
            logger.info("Scheduler Job: No due reminders found.")
            return

        logger.info(f"Scheduler Job: Found {len(due_reminders)} due reminders.")
        for reminder in due_reminders:
            # --- Simulate Sending ---
            # In a real app, this would involve email, SMS, etc.
            # For now, we log and include patient details if available.
            try:
                patient = crud.get_patient(db, reminder.patient_id)
                patient_info = f"Patient ID {reminder.patient_id} (Synthea ID: {patient.synthea_id if patient else 'N/A'})"
                # TODO: Implement actual email sending using reminder.method and patient email if available
                # (Need to add email field to Patient model/schema first)
                logger.info(f"---> Sending Reminder {reminder.id}: To {patient_info} - Message: '{reminder.message}' (Due: {reminder.due_at}) <---")

                # --- Mark as sent (or delete) ---
                # Option 1: Delete after sending (simple)
                # crud.delete_reminder(db, reminder.id)
                # logger.info(f"Scheduler Job: Deleted reminder {reminder.id}")

                # Option 2: Mark as sent (add a 'sent_at' field to Reminder model)
                # Ensure scheduler timezone is available if needed here, pass from calling context or re-initialize
                # For now, using UTC directly for marking sent time, or adjust if needed
                # Or get timezone from settings again if scheduler object isn't easily accessible
                reminder.sent_at = datetime.now(pytz.timezone(settings.DEFAULT_TIMEZONE)) # Use configured timezone
                db.commit()
                logger.info(f"Scheduler Job: Marked reminder {reminder.id} as sent.")

            except Exception as send_err:
                logger.error(f"Scheduler Job: Error processing reminder {reminder.id}: {send_err}", exc_info=True)
                db.rollback() # Rollback changes for this specific reminder

    except Exception as e:
        logger.error(f"Scheduler Job: Error querying due reminders: {e}", exc_info=True)
        db.rollback() # Rollback any potential session changes
    finally:
        db.close()
        logger.info("Scheduler Job: Finished check_and_send_reminders.")

# --- Scheduler Control Functions ---

def start_scheduler(timezone: str, interval_minutes: int):
    """Initializes and starts the scheduler, taking config values as args."""
    global scheduler # Need to modify the global variable
    try:
        # Initialize scheduler here if it hasn't been already
        if scheduler is None:
            # Use the passed-in timezone
            logger.info(f"Initializing scheduler with timezone: {timezone}")
            scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone=timezone # Use passed-in timezone
            )

        if not scheduler.running:
            # Add the job to run every X minutes (use passed-in interval)
            scheduler.add_job(
                check_and_send_reminders,
                'interval',
                minutes=interval_minutes, # Use passed-in interval
                id='reminder_check_job', # Assign an ID to prevent duplicates
                replace_existing=True # Replace if job with same ID exists
            )
            scheduler.start()
            # Use passed-in interval in log message
            logger.info(f"Scheduler started. Reminder check interval: {interval_minutes} minutes.")
        else:
            logger.info("Scheduler is already running.")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
        # Handle error appropriately, maybe prevent app startup

def stop_scheduler():
    """Stops the scheduler gracefully."""
    global scheduler # Need to access the global variable
    try:
        if scheduler and scheduler.running: # Check if scheduler exists and is running
            scheduler.shutdown()
            logger.info("Scheduler stopped.")
        else:
            logger.info("Scheduler was not running.")
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}", exc_info=True) 