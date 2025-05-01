from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import datetime

# --- Base Schemas (for common fields) ---
class UserBase(BaseModel):
    # Assuming user ID comes from auth later (e.g., Firebase UID)
    user_id: str = Field(..., description="Unique identifier for the user")

# --- Chat Schemas ---
class ChatRequest(UserBase):
    message: str = Field(..., description="The user's message to the assistant")
    session_id: Optional[str] = Field(None, description="Optional session ID to maintain context across multiple requests")
    # We might add history here later if frontend manages it
    # history: Optional[List[Dict[str, str]]] = None

class ChatResponse(BaseModel):
    reply: str = Field(..., description="The assistant's response message")
    session_id: Optional[str] = Field(None, description="Session ID used for the interaction")
    # Restore original sources definition
    # sources: Optional[List[str]] = Field(None, description="List of source identifiers cited in the reply")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="List of sources cited in the reply (e.g., {'title': '...', 'url': '...'})" )
    triage_tag: Optional[str] = Field(None, description="Symptom triage result (e.g., ER, DoctorSoon, SelfCare)")

# --- Scheduling Schemas (Example Placeholders) ---
class AppointmentBase(BaseModel):
    patient_id: int # Or str, depending on Patient model ID type
    appointment_time: datetime.datetime
    provider_name: Optional[str] = None
    reason: Optional[str] = None

class AppointmentCreate(AppointmentBase):
    pass # Inherits fields from Base

class AppointmentRead(AppointmentBase):
    id: int
    duration_minutes: int
    status: str

    class Config:
        from_attributes = True # Updated from orm_mode

# --- Reminder Schemas (Example Placeholders) ---
class ReminderBase(BaseModel):
    # Make patient_id optional for guest users
    patient_id: Optional[int] = None # Or str
    reminder_type: str = Field(..., description="Type of reminder (e.g., medication, appointment)")
    due_at: datetime.datetime
    message: str
    method: Optional[str] = 'email'

class ReminderCreate(ReminderBase):
    pass

class ReminderRead(ReminderBase):
    id: int
    sent_at: Optional[datetime.datetime] = None
    # patient_id is inherited from ReminderBase and is already Optional

    class Config:
        from_attributes = True # Updated from orm_mode

# Add other schemas as needed (e.g., for Patient, Medication if exposing via API) 