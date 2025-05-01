from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from backend import schemas, crud, models # Import models
from backend.database import get_db
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Note: Background task for sending reminders (e.g., email) is separate
# from CRUD operations. A real system would use Celery/APScheduler.
# async def send_reminder_email_task(email_address: str, message: str):
#    ...

@router.post("", response_model=schemas.ReminderRead)
def create_reminder(
    reminder: schemas.ReminderCreate,
    # background_tasks: BackgroundTasks, # Keep for later if needed
    db: Session = Depends(get_db)
):
    """Create a new reminder using CRUD function."""
    # Validate patient exists
    db_patient = crud.get_patient(db, patient_id=reminder.patient_id)
    if not db_patient:
        logger.warning(f"Attempt to create reminder for non-existent patient ID: {reminder.patient_id}")
        raise HTTPException(status_code=404, detail=f"Patient with ID {reminder.patient_id} not found")

    logger.info(f"Creating reminder for patient {reminder.patient_id} due at {reminder.due_at}")
    try:
        db_reminder = crud.create_reminder(db=db, reminder=reminder)
        logger.info(f"Reminder created with ID: {db_reminder.id}")
        # Add background task here if needed based on due_at
        # e.g., if reminder.due_at < datetime.utcnow() + timedelta(hours=1):
        #    background_tasks.add_task(send_reminder_email_task, "user@example.com", reminder.message)
        return db_reminder
    except Exception as e:
        logger.error(f"Failed to create reminder: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error creating reminder.")

@router.get("/patient/{patient_id}", response_model=List[schemas.ReminderRead])
def read_patient_reminders(
    patient_id: int, # Or str
    skip: int = 0,
    limit: int = 100,
    include_sent: bool = False,
    db: Session = Depends(get_db)
):
    """Retrieve reminders for a specific patient using CRUD."""
    logger.info(f"Fetching reminders for patient {patient_id} (include_sent={include_sent}) with skip={skip}, limit={limit}")
    # Validate patient exists
    db_patient = crud.get_patient(db, patient_id=patient_id)
    if not db_patient:
         logger.warning(f"Attempt to read reminders for non-existent patient ID: {patient_id}")
         raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found")

    try:
        reminders = crud.get_reminders_by_patient(
            db, patient_id=patient_id, skip=skip, limit=limit, include_sent=include_sent
        )
        logger.info(f"Found {len(reminders)} reminders for patient {patient_id}")
        return reminders
    except Exception as e:
        logger.error(f"Failed to read reminders for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error reading reminders.")

# Optional: Add GET by ID and DELETE endpoints
@router.get("/{reminder_id}", response_model=schemas.ReminderRead)
def read_reminder(
    reminder_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve a specific reminder by its ID."""
    logger.info(f"Fetching reminder with ID: {reminder_id}")
    db_reminder = crud.get_reminder(db, reminder_id=reminder_id)
    if db_reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return db_reminder

@router.delete("/{reminder_id}", status_code=204)
def delete_reminder_endpoint(
    reminder_id: int,
    db: Session = Depends(get_db)
):
    """Delete a specific reminder by its ID."""
    logger.info(f"Attempting to delete reminder with ID: {reminder_id}")
    deleted = crud.delete_reminder(db, reminder_id=reminder_id)
    if not deleted:
        logger.warning(f"Attempt to delete non-existent reminder ID: {reminder_id}")
        raise HTTPException(status_code=404, detail="Reminder not found")
    logger.info(f"Successfully deleted reminder ID: {reminder_id}")
    return 