import os
import sys
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, OperationalError
from dotenv import load_dotenv
import logging
from datetime import datetime

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables (.env file in project root)
load_dotenv(dotenv_path=os.path.join(project_root, '.env'))

# Import SQLAlchemy models
from backend.models import Base, Patient, Medication, Appointment # Add other models if needed

# --- Constants ---
# Directory containing Synthea CSV output files
SYNTHEA_OUTPUT_DIR = os.path.join(project_root, "data", "synthea_output")
# Adjust filenames based on actual Synthea output
PATIENTS_CSV = os.path.join(SYNTHEA_OUTPUT_DIR, "patients.csv")
MEDICATIONS_CSV = os.path.join(SYNTHEA_OUTPUT_DIR, "medications.csv")
APPOINTMENTS_CSV = os.path.join(SYNTHEA_OUTPUT_DIR, "appointments.csv") # Synthea might not have a direct appointments CSV, may need to derive from encounters
ENCOUNTERS_CSV = os.path.join(SYNTHEA_OUTPUT_DIR, "encounters.csv") # Often used for appointments

# Database connection
DATABASE_URL = os.getenv("POSTGRES_DB_URL")

# --- Database Setup ---
def get_db_session():
    """Creates and returns a new SQLAlchemy Session."""
    if not DATABASE_URL:
        logging.error("POSTGRES_DB_URL not set in environment variables.")
        sys.exit(1)
    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        # Verify connection
        with engine.connect():
            logging.info("Database connection verified.")
        return SessionLocal()
    except OperationalError as e:
        logging.error(f"Database connection failed: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error creating database session: {e}")
        sys.exit(1)

# --- Data Processing Functions ---

def load_patients(session, csv_path):
    """Loads patient data from Synthea CSV into the database."""
    logging.info(f"Loading patients from {csv_path}...")
    if not os.path.exists(csv_path):
        logging.error(f"Patient CSV not found: {csv_path}")
        return 0

    try:
        df = pd.read_csv(csv_path, parse_dates=['BIRTHDATE'])
        logging.info(f"Read {len(df)} rows from {csv_path}")
        count = 0
        for _, row in df.iterrows():
            # Map Synthea columns to Patient model columns
            # Adjust column names ('Id', 'FIRST', 'LAST', 'BIRTHDATE') based on your Synthea output
            patient = Patient(
                synthea_id=row['Id'],
                first_name=row['FIRST'],
                last_name=row['LAST'],
                dob=row['BIRTHDATE'].date() # Convert timestamp to date
                # Add other fields like GENDER, ADDRESS etc. if needed
            )
            session.add(patient)
            try:
                # Commit individually or in batches to handle potential duplicates
                session.commit()
                count += 1
            except IntegrityError:
                session.rollback()
                logging.warning(f"Patient with Synthea ID {row['Id']} likely already exists. Skipping.")
            except Exception as e:
                session.rollback()
                logging.error(f"Error adding patient {row['Id']}: {e}")
                # Decide whether to continue or stop on error

        logging.info(f"Successfully loaded {count} new patients.")
        return count
    except KeyError as e:
        logging.error(f"Missing expected column in {csv_path}: {e}. Please check Synthea output format.")
        return 0
    except Exception as e:
        logging.error(f"Error processing {csv_path}: {e}")
        session.rollback() # Rollback any partial commit from this function
        return 0

def load_medications(session, csv_path):
    """Loads medication data from Synthea CSV into the database."""
    logging.info(f"Loading medications from {csv_path}...")
    if not os.path.exists(csv_path):
        logging.error(f"Medication CSV not found: {csv_path}")
        return 0

    try:
        df = pd.read_csv(csv_path, parse_dates=['START', 'STOP'])
        logging.info(f"Read {len(df)} rows from {csv_path}")
        # We need patient internal IDs, query them first
        patient_map = {p.synthea_id: p.id for p in session.query(Patient.id, Patient.synthea_id).all()}
        count = 0

        for _, row in df.iterrows():
            # Adjust Synthea column names ('PATIENT', 'DESCRIPTION', 'START', 'STOP', 'DISPENSES', etc.) as needed
            synthea_patient_id = row['PATIENT']
            if synthea_patient_id not in patient_map:
                logging.warning(f"Patient {synthea_patient_id} for medication not found in DB. Skipping medication: {row.get('DESCRIPTION', 'N/A')}")
                continue

            patient_db_id = patient_map[synthea_patient_id]

            # Dosage/Frequency might need parsing from 'REASONDESCRIPTION' or other fields if not direct
            med = Medication(
                patient_id=patient_db_id,
                med_name=row['DESCRIPTION'],
                start_date=row['START'].date(),
                end_date=row['STOP'].date() if pd.notna(row['STOP']) else None,
                dosage=str(row.get('TOTALCOST', '')), # Placeholder - Synthea might not have simple dosage/freq
                frequency=str(row.get('PAYER_COVERAGE', '')) # Placeholder
            )
            session.add(med)
            count += 1

        session.commit() # Commit all medications for simplicity here, batching is better for large data
        logging.info(f"Successfully loaded {count} medication records.")
        return count

    except KeyError as e:
        logging.error(f"Missing expected column in {csv_path}: {e}. Please check Synthea output format.")
        return 0
    except Exception as e:
        logging.error(f"Error processing {csv_path}: {e}")
        session.rollback()
        return 0

def load_appointments(session, csv_path):
    """Loads appointment data (derived from encounters) from Synthea CSV."""
    logging.info(f"Loading appointments from {csv_path} (Synthea encounters)...")
    if not os.path.exists(csv_path):
        logging.error(f"Encounters CSV not found: {csv_path}")
        return 0

    try:
        # Adjust date parsing columns based on Synthea output
        df = pd.read_csv(csv_path, parse_dates=['START', 'STOP'])
        logging.info(f"Read {len(df)} rows from {csv_path}")

        patient_map = {p.synthea_id: p.id for p in session.query(Patient.id, Patient.synthea_id).all()}
        count = 0

        # Filter for relevant encounter types if needed (e.g., ENCOUNTERCLASS = 'ambulatory')
        # df_appointments = df[df['ENCOUNTERCLASS'] == 'ambulatory'].copy()
        df_appointments = df # Process all for now

        for _, row in df_appointments.iterrows():
            # Adjust Synthea column names ('PATIENT', 'PROVIDER', 'START', 'REASONDESCRIPTION')
            synthea_patient_id = row['PATIENT']
            if synthea_patient_id not in patient_map:
                logging.warning(f"Patient {synthea_patient_id} for encounter not found in DB. Skipping appointment.")
                continue

            patient_db_id = patient_map[synthea_patient_id]
            start_time = row['START']
            # Calculate duration if possible, otherwise use default
            # Add error handling for invalid STOP data
            duration = 30 # Default duration
            try:
                if pd.notna(row['STOP']) and pd.notna(start_time):
                    # Attempt conversion only if STOP is not null
                    stop_time = pd.to_datetime(row['STOP'], errors='coerce') # Coerce errors to NaT (Not a Time)
                    if pd.notna(stop_time):
                         # Ensure start_time is also timezone-aware or naive consistently if needed
                         # Assuming both are pandas Timestamps
                         calculated_duration = (stop_time - start_time).total_seconds() / 60
                         # Ensure duration is not negative or excessively large, use default otherwise
                         if calculated_duration > 0 and calculated_duration < (60*24): # Max 1 day appointment
                             duration = calculated_duration
                         else:
                             logging.debug(f"Invalid calculated duration ({calculated_duration}) for encounter ID {row.get('Id', 'N/A')}. Using default.")
                    else:
                        logging.debug(f"Could not parse STOP time ('{row['STOP']}') for encounter ID {row.get('Id', 'N/A')}. Using default duration.")
                # else: keep default duration if STOP or START is missing
            except Exception as e:
                logging.warning(f"Error calculating duration for encounter ID {row.get('Id', 'N/A')} (START: {start_time}, STOP: {row.get('STOP', 'N/A')}): {e}. Using default duration.")
                duration = 30 # Reset to default on any unexpected error

            appt = Appointment(
                patient_id=patient_db_id,
                appointment_time=start_time,
                duration_minutes=int(duration),
                provider_name=row.get('PROVIDER', 'Unknown'), # Provider ID might need mapping to names
                # Ensure NaN from pandas is converted to None for SQL compatibility
                reason=None if pd.isna(row.get('REASONDESCRIPTION')) else row.get('REASONDESCRIPTION'),
                status='completed' # Assuming encounters are completed appointments
            )
            session.add(appt)
            count += 1

        session.commit()
        logging.info(f"Successfully loaded {count} appointment records (from encounters).")
        return count

    except KeyError as e:
        logging.error(f"Missing expected column in {csv_path}: {e}. Please check Synthea output format.")
        return 0
    except Exception as e:
        logging.error(f"Error processing {csv_path}: {e}")
        session.rollback()
        return 0

# --- Main Execution --- #
def main():
    logging.info("--- Starting Synthea Data Ingestion for Postgres ---")
    session = get_db_session()

    if not session:
        logging.error("Failed to get database session. Exiting.")
        return

    try:
        # Load data in order (Patients first due to foreign keys)
        logging.info("Attempting to load patients (warnings about existing patients are expected if run previously).")
        patients_processed_count = load_patients(session, PATIENTS_CSV)
        # We proceed even if patients_processed_count is 0, as patients might already exist from a previous run.
        # We only stop if there was a fatal error preventing patient loading/querying.

        # Query existing patients needed for linking foreign keys
        logging.info("Querying patient map for linking...")
        patient_map = {p.synthea_id: p.id for p in session.query(Patient.id, Patient.synthea_id).all()}

        if not patient_map:
            logging.error("Could not retrieve patient mapping from database. Cannot load medications or appointments. Exiting.")
            sys.exit(1)
        else:
            logging.info(f"Retrieved {len(patient_map)} patient mappings.")

        meds_loaded = load_medications(session, MEDICATIONS_CSV)
        appts_loaded = load_appointments(session, ENCOUNTERS_CSV) # Using encounters for appointments

        logging.info("--- Synthea Ingestion Summary ---")
        logging.info(f"Patients processed in this run (newly added or skipped): {patients_processed_count}")
        logging.info(f"Medications loaded: {meds_loaded}")
        logging.info(f"Appointments loaded: {appts_loaded}")
        logging.info("--- Ingestion Complete ---")

    except Exception as e:
        logging.error(f"An error occurred during the main ingestion process: {e}")
        session.rollback() # Ensure rollback on any unexpected error
    finally:
        if session:
            session.close()
            logging.info("Database session closed.")

if __name__ == "__main__":
    main() 