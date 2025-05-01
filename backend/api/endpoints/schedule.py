from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend import schemas, crud, models # Import models for type hinting
from backend.database import get_db
import logging # Import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=schemas.AppointmentRead)
def create_appointment(
    appointment: schemas.AppointmentCreate,
    db: Session = Depends(get_db)
):
    """Create a new appointment using CRUD function."""
    # Validate patient exists
    db_patient = crud.get_patient(db, patient_id=appointment.patient_id)
    if not db_patient:
        logger.warning(f"Attempt to create appointment for non-existent patient ID: {appointment.patient_id}")
        raise HTTPException(status_code=404, detail=f"Patient with ID {appointment.patient_id} not found")

    # TODO: Add more complex logic here - check for conflicts, provider availability etc.
    logger.info(f"Creating appointment for patient {appointment.patient_id} at {appointment.appointment_time}")
    try:
        db_appointment = crud.create_appointment(db=db, appointment=appointment)
        logger.info(f"Appointment created with ID: {db_appointment.id}")
        return db_appointment # SQLAlchemy model is automatically converted by Pydantic
    except Exception as e:
        logger.error(f"Failed to create appointment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error creating appointment.")

@router.get("/patient/{patient_id}", response_model=List[schemas.AppointmentRead])
def read_patient_appointments(
    patient_id: int, # Or str if your Patient ID is string
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Retrieve appointments for a specific patient using CRUD."""
    logger.info(f"Fetching appointments for patient {patient_id} with skip={skip}, limit={limit}")
    # Validate patient exists (optional, but good practice)
    db_patient = crud.get_patient(db, patient_id=patient_id)
    if not db_patient:
         logger.warning(f"Attempt to read appointments for non-existent patient ID: {patient_id}")
         raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found")

    try:
        appointments = crud.get_appointments_by_patient(
            db, patient_id=patient_id, skip=skip, limit=limit
        )
        logger.info(f"Found {len(appointments)} appointments for patient {patient_id}")
        return appointments
    except Exception as e:
        logger.error(f"Failed to read appointments for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error reading appointments.")

# Example: Add endpoint to get a specific appointment
@router.get("/{appointment_id}", response_model=schemas.AppointmentRead)
def read_appointment(
    appointment_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve a specific appointment by its ID."""
    logger.info(f"Fetching appointment with ID: {appointment_id}")
    db_appointment = crud.get_appointment(db, appointment_id=appointment_id)
    if db_appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return db_appointment

# Example: Add endpoint to delete an appointment
@router.delete("/{appointment_id}", status_code=204) # 204 No Content on successful delete
def delete_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db)
):
    """Delete a specific appointment by its ID."""
    logger.info(f"Attempting to delete appointment with ID: {appointment_id}")
    deleted = crud.delete_appointment(db, appointment_id=appointment_id)
    if not deleted:
        logger.warning(f"Attempt to delete non-existent appointment ID: {appointment_id}")
        raise HTTPException(status_code=404, detail="Appointment not found")
    logger.info(f"Successfully deleted appointment ID: {appointment_id}")
    return # Return None for 204 status code

# Add other scheduling endpoints as needed (GET specific appt, PUT to update, DELETE) 