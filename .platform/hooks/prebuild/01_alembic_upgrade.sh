#!/bin/bash

echo "Running Alembic migrations..."

# Activate virtual environment if needed (EB Docker platform usually runs commands directly)
# source /path/to/your/venv/bin/activate

# Navigate to the app directory where alembic.ini is located
# (The working directory for hooks might vary, adjust if needed)
# cd /var/app/current # Example path on Amazon Linux 2 EB platforms

# Run the upgrade command
# Ensure POSTGRES_DB_URL is available as an environment variable in the EB environment
alembic upgrade head

echo "Alembic migrations finished." 