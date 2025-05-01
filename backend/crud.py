from sqlalchemy.orm import Session
from typing import List, Optional

from . import models, schemas
from datetime import datetime

# --- Patient CRUD --- #

def get_patient(db: Session, patient_id: int) -> Optional[models.Patient]:
    """Retrieve a single patient by their internal database ID."""
    return db.query(models.Patient).filter(models.Patient.id == patient_id).first()

def get_patient_by_synthea_id(db: Session, synthea_id: str) -> Optional[models.Patient]:
    """Retrieve a single patient by their Synthea ID."""
    return db.query(models.Patient).filter(models.Patient.synthea_id == synthea_id).first()

def get_patients(db: Session, skip: int = 0, limit: int = 100) -> List[models.Patient]:
    """Retrieve a list of patients with pagination."""
    return db.query(models.Patient).offset(skip).limit(limit).all()

# Note: Patient creation is typically handled by the ingestion script.
# We might add update/delete later if needed.

# --- Appointment CRUD --- #

def get_appointment(db: Session, appointment_id: int) -> Optional[models.Appointment]:
    """Retrieve a single appointment by its ID."""
    return db.query(models.Appointment).filter(models.Appointment.id == appointment_id).first()

def get_appointments_by_patient(
    db: Session, patient_id: int, skip: int = 0, limit: int = 100
) -> List[models.Appointment]:
    """Retrieve appointments for a specific patient with pagination."""
    return (
        db.query(models.Appointment)
        .filter(models.Appointment.patient_id == patient_id)
        .order_by(models.Appointment.appointment_time.desc()) # Show most recent first
        .offset(skip)
        .limit(limit)
        .all()
    )

def create_appointment(
    db: Session, appointment: schemas.AppointmentCreate
) -> models.Appointment:
    """Create a new appointment record in the database."""
    db_appointment = models.Appointment(
        patient_id=appointment.patient_id,
        appointment_time=appointment.appointment_time,
        provider_name=appointment.provider_name,
        reason=appointment.reason,
        duration_minutes=30, # Default or calculate based on provider/reason later
        status="scheduled" # Default status
    )
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment) # Get the ID assigned by the database
    return db_appointment

def update_appointment_status(
    db: Session, appointment_id: int, status: str
) -> Optional[models.Appointment]:
    """Update the status of an existing appointment (e.g., 'confirmed', 'cancelled')."""
    db_appointment = get_appointment(db, appointment_id=appointment_id)
    if db_appointment:
        db_appointment.status = status
        db.commit()
        db.refresh(db_appointment)
    return db_appointment

def delete_appointment(db: Session, appointment_id: int) -> bool:
    """Delete an appointment by its ID. Returns True if deleted, False otherwise."""
    db_appointment = get_appointment(db, appointment_id=appointment_id)
    if db_appointment:
        db.delete(db_appointment)
        db.commit()
        return True
    return False

# --- Reminder CRUD --- #

def get_reminder(db: Session, reminder_id: int) -> Optional[models.Reminder]:
    """Retrieve a single reminder by its ID."""
    return db.query(models.Reminder).filter(models.Reminder.id == reminder_id).first()

def get_reminders_by_patient(
    db: Session, patient_id: int, skip: int = 0, limit: int = 100, include_sent: bool = False
) -> List[models.Reminder]:
    """Retrieve reminders for a specific patient with pagination."""
    query = db.query(models.Reminder).filter(models.Reminder.patient_id == patient_id)
    if not include_sent:
        query = query.filter(models.Reminder.sent_at == None)
    return (
        query
        .order_by(models.Reminder.due_at.asc()) # Show soonest first
        .offset(skip)
        .limit(limit)
        .all()
    )

def create_reminder(db: Session, reminder: schemas.ReminderCreate) -> models.Reminder:
    """Create a new reminder record in the database."""
    db_reminder = models.Reminder(
        patient_id=reminder.patient_id,
        reminder_type=reminder.reminder_type,
        due_at=reminder.due_at,
        message=reminder.message,
        method=reminder.method
    )
    db.add(db_reminder)
    db.commit()
    db.refresh(db_reminder)
    return db_reminder

def get_due_reminders(db: Session, cutoff_time: datetime) -> List[models.Reminder]:
    """
    Retrieve all reminders that are due on or before the cutoff_time
    and have not yet been sent (sent_at is NULL).
    """
    return (
        db.query(models.Reminder)
        .filter(
            models.Reminder.due_at <= cutoff_time,
            models.Reminder.sent_at == None  # Use == None for NULL check in SQLAlchemy
        )
        .order_by(models.Reminder.due_at.asc())
        .all()
    )

def mark_reminder_sent(db: Session, reminder_id: int) -> Optional[models.Reminder]:
    """Update the sent_at timestamp for a reminder."""
    db_reminder = get_reminder(db, reminder_id=reminder_id)
    if db_reminder:
        db_reminder.sent_at = datetime.utcnow()
        db.commit()
        db.refresh(db_reminder)
    return db_reminder

def delete_reminder(db: Session, reminder_id: int) -> bool:
    """Delete a reminder by its ID. Returns True if deleted, False otherwise."""
    db_reminder = get_reminder(db, reminder_id=reminder_id)
    if db_reminder:
        db.delete(db_reminder)
        db.commit()
        return True
    return False 