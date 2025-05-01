# Stage 1: Build Environment
# Use an official Python runtime as a parent image
FROM python:3.11-slim as builder

# Set the working directory in the container
WORKDIR /app

# Install build dependencies if any (e.g., for psycopg2)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
# (Uncomment above if psycopg2 build fails without system deps)

# Install pip dependencies
# Copy only requirements to leverage Docker cache
COPY requirements.txt .
# Ensure pip is up-to-date and install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code
COPY ./backend /app/backend
# Copy Alembic configuration
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
# Copy scripts needed for initialization/ingestion
COPY ./scripts /app/scripts
# Copy data needed ONLY for vector DB ingestion (if script reads from here)
COPY ./data/downloaded /app/data/downloaded
# (Adjust path above if your ingest_vector_db.py reads from a different location)
COPY ./data/symptom_rules.json /app/data/symptom_rules.json
# Stage 2: Production Environment
FROM python:3.11-slim

WORKDIR /app

# Copy installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code, alembic config, scripts, and necessary data from builder
COPY --from=builder /app/backend /app/backend
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/scripts /app/scripts
COPY --from=builder /app/data/downloaded /app/data/downloaded
COPY --from=builder /app/data/symptom_rules.json /app/data/symptom_rules.json

# Copy the entrypoint script
COPY ./entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# COPY .env /app/.env # --- DO NOT COPY .env --- Use EB Environment Properties

# Expose the port the app runs on
EXPOSE 8000

# Use the entrypoint script to run initialization then the app
ENTRYPOINT ["/app/entrypoint.sh"]

# CMD is now defined inside entrypoint.sh
# CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"] 