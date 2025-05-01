#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# Run Vector DB Ingestion
# Ensure necessary environment variables (like GOOGLE_API_KEY) are available
# The paths inside the script should align with the WORKDIR and COPY commands in Dockerfile
echo "Running vector database ingestion script..."
python scripts/ingest_vector_db.py
echo "Vector database ingestion complete."

# Start the main application (Uvicorn)
echo "Starting Uvicorn server..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 