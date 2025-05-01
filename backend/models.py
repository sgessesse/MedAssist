from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Date
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import os
from dotenv import load_dotenv

load_dotenv()

# Base class for SQLAlchemy models
Base = declarative_base()

# Database connection setup (consider moving to a separate db module later)
# DATABASE_URL = os.getenv("POSTGRES_DB_URL", "postgresql://user:password@host:port/dbname") # Default is just a placeholder
# engine = create_engine(DATABASE_URL)

# --- EHR Simulation Tables ---

class Patient(Base):
    __tablename__ = 'patients'
    id = Column(Integer, primary_key=True) # Or String if Synthea uses non-integer IDs
    synthea_id = Column(String, unique=True, index=True) # To link back to Synthea data if needed
    first_name = Column(String)
    last_name = Column(String)
    dob = Column(Date)
    # Add other relevant patient demographics from Synthea if needed (gender, address, etc.)

    # Relationships (optional but useful)
    medications = relationship("Medication", back_populates="patient")
    appointments = relationship("Appointment", back_populates="patient")
    reminders = relationship("Reminder", back_populates="patient")

class Medication(Base):
    __tablename__ = 'medications'
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
    med_name = Column(String, nullable=False)
    dosage = Column(String)
    frequency = Column(String) # e.g., "daily", "twice a day"
    start_date = Column(Date)
    end_date = Column(Date, nullable=True) # Null if ongoing
    # Consider adding: prescribing_doctor, reason, status (active/inactive)

    patient = relationship("Patient", back_populates="medications")

class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
    appointment_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30)
    provider_name = Column(String) # Or ForeignKey to a 'providers' table
    reason = Column(Text, nullable=True)
    status = Column(String, default='scheduled') # e.g., scheduled, completed, cancelled

    patient = relationship("Patient", back_populates="appointments")

# --- Application-Specific Tables ---

class Reminder(Base):
    __tablename__ = 'reminders'
    id = Column(Integer, primary_key=True)
    # Make patient_id nullable to allow guest reminders
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=True)
    reminder_type = Column(String, nullable=False) # e.g., 'medication', 'appointment'
    due_at = Column(DateTime, nullable=False)
    message = Column(Text) # e.g., "Take your 10mg Lisinopril"
    sent_at = Column(DateTime, nullable=True) # Null until sent
    method = Column(String, default='email') # 'email', 'sms'

    patient = relationship("Patient", back_populates="reminders")

class AuditLog(Base):
    __tablename__ = 'audit_log'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(String, index=True) # From Firebase Auth or session
    session_id = Column(String, index=True, nullable=True) # Optional: to group interactions
    prompt = Column(Text)
    response = Column(Text)
    tool_calls = Column(JSON, nullable=True) # Store structured tool usage info
    safety_assessment = Column(JSON, nullable=True) # Store safety filter results
    latency_ms = Column(Integer, nullable=True)

# --- Potential Future Tables (as needed) ---
# class Provider(Base): ...
# class AvailabilitySlot(Base): ... # For scheduling

# Function to create tables (can be called from init script)
# def create_tables():
#     Base.metadata.create_all(bind=engine)

# if __name__ == "__main__":
#     # Example usage: Create tables if script is run directly
#     print("Creating database tables...")
#     # Make sure DATABASE_URL is correctly set in your .env file
#     # or provide a default connection string for local dev
#     if not DATABASE_URL or DATABASE_URL == "postgresql://user:password@host:port/dbname":
#         print("Warning: DATABASE_URL not set or using placeholder. Cannot connect to DB.")
#     else:
#         engine = create_engine(DATABASE_URL)
#         try:
#             Base.metadata.create_all(bind=engine)
#             print("Tables created successfully (if they didn't exist).")
#         except Exception as e:
#             print(f"Error creating tables: {e}") 