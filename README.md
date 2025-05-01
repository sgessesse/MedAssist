# MedAssist - AI Medical Assistant Chatbot

## 1. Overview

MedAssist is a virtual medical assistant chatbot built with FastAPI (Python) for the backend and Next.js (React/TypeScript) for the frontend. It leverages Large Language Models (LLMs) via Google Gemini and LangChain, combined with Retrieval-Augmented Generation (RAG) from a curated medical knowledge base (stored in ChromaDB) to provide informative answers, basic symptom triage, appointment scheduling assistance, and reminder setting.

**Disclaimer:** This application simulates assistant functionalities and is **NOT** intended as a substitute for professional medical advice, diagnosis, or treatment. Always consult with a qualified healthcare provider for any health concerns.

## 2. Features

*   **Conversational Interface:** Simple chat UI for interaction.
*   **Medical Q&A:** Answers general medical questions using RAG based on ingested data (e.g., MedlinePlus).
*   **Symptom Triage:** Provides basic triage suggestions (Self-Care, Doctor Soon, ER) based on user-described symptoms and predefined rules. Results are visually indicated by chat bubble color.
*   **Appointment Scheduling:** Allows registered/known users to request appointments via chat (saved to a PostgreSQL database).
*   **Reminder Setting:** Allows users (including guests) to set reminders via chat (saved to PostgreSQL). Guest reminders are logged but not delivered externally.
*   **Guest Mode:** Allows users to interact without registration, generating a temporary session ID.
*   **Contextual Memory:** Maintains conversation history within a session for follow-up questions.

## 3. Technical Stack

*   **Backend:**
    *   Framework: FastAPI
    *   Language: Python 3.11+
    *   LLM / Orchestration: Google Gemini (`gemini-2.0-flash`), LangChain
    *   Database: PostgreSQL
    *   ORM: SQLAlchemy
    *   Migrations: Alembic
    *   Vector Store: ChromaDB
    *   Background Tasks: APScheduler (for reminder checks)
*   **Frontend:**
    *   Framework: Next.js (App Router)
    *   Language: TypeScript
    *   Styling: Tailwind CSS
*   **Containerization:** Docker

## 4. Project Structure

```
MedAssist/
├── alembic/               # Alembic migration scripts & config
├── backend/
│   ├── api/               # FastAPI endpoint routers
│   ├── core/              # Core logic (config, agent, scheduler)
│   ├── __init__.py
│   ├── crud.py            # Database CRUD functions
│   ├── database.py        # SQLAlchemy setup
│   ├── main.py            # FastAPI app entrypoint
│   ├── models.py          # SQLAlchemy ORM models
│   └── schemas.py         # Pydantic schemas
├── data/
│   ├── chroma_db/         # Vector store persistence (ignored by git)
│   ├── downloaded/        # Raw downloaded data (e.g., MedlinePlus) (ignored)
│   └── synthea_output/    # Synthea patient data (ignored)
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── app/           # Next.js App Router pages
│   │   └── components/    # React components (ChatInterface)
│   ├── next.config.js
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── scripts/               # Utility scripts (DB init, ingestion)
├── .env                   # Environment variables (ignored)
├── .gitignore             # Files ignored by git
├── alembic.ini            # Alembic configuration
├── backend/Dockerfile     # Dockerfile for backend
├── frontend/Dockerfile    # Dockerfile for frontend
├── README.md              # This file
└── requirements.txt       # Python dependencies
```

## 5. Setup and Running

### Prerequisites

*   Docker & Docker Compose (or just Docker Desktop)
*   Python 3.11+
*   Node.js (v18+ recommended)
*   Access to Google Gemini API (requires an API key)
*   Git

### Setup Steps

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd MedAssist
    ```

2.  **Configure Environment Variables:**
    *   Copy the `.env.example` file (if provided) or create a `.env` file in the project root.
    *   Set the required environment variables:
        *   `GOOGLE_API_KEY`: Your API key for Google Gemini.
        *   `POSTGRES_DB_URL`: The connection string for your PostgreSQL database (see Step 3).
        *   `DEFAULT_TIMEZONE`: (Optional, defaults to UTC) e.g., `America/New_York`
        *   `REMINDER_CHECK_INTERVAL_MINUTES`: (Optional, defaults to 1)

3.  **Start PostgreSQL Database:**
    *   Use Docker to start a PostgreSQL instance. A named volume is recommended for data persistence.
        ```bash
        # Replace YOUR_CHOSEN_PASSWORD with a secure password
        docker run -d \
            --name medassist-postgres \
            -e POSTGRES_PASSWORD=YOUR_CHOSEN_PASSWORD \
            -e POSTGRES_USER=postgres \
            -e POSTGRES_DB=medassist_db \
            -p 5432:5432 \
            -v medassist_pgdata:/var/lib/postgresql/data \
            postgres:latest
        ```
    *   Ensure your `POSTGRES_DB_URL` in `.env` matches these credentials:
        `postgresql://postgres:YOUR_CHOSEN_PASSWORD@localhost:5432/medassist_db`

4.  **Backend Setup:**
    *   Navigate to the project root.
    *   Create and activate a Python virtual environment (recommended):
        ```bash
        python -m venv .venv
        source .venv/bin/activate  # Linux/macOS
        # .venv\Scripts\activate    # Windows
        ```
    *   Install Python dependencies:
        ```bash
        pip install -r requirements.txt
        ```
    *   Initialize the database schema using Alembic:
        ```bash
        # Ensure .env file is correctly configured first
        alembic upgrade head
        ```
    *   *(Optional - Dev Only)* Ingest Synthea patient data (if needed for testing):
        ```bash
        python scripts/ingest_postgres_db.py
        ```
    *   Ingest data into the vector store:
        ```bash
        python scripts/ingest_vector_db.py
        ```

5.  **Frontend Setup:**
    *   Navigate to the frontend directory:
        ```bash
        cd frontend
        ```
    *   Install Node.js dependencies:
        ```bash
        npm install # or yarn install or pnpm install
        ```

### Running the Application

1.  **Run the Backend (FastAPI):**
    *   From the project root directory (with virtual environment active):
        ```bash
        uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
        ```
    *   The backend API will be available at `http://localhost:8000`.

2.  **Run the Frontend (Next.js):**
    *   From the `frontend/` directory:
        ```bash
        npm run dev # or yarn dev or pnpm dev
        ```
    *   The frontend application will be available at `http://localhost:3000`.

### Running with Docker (Alternative)

(Requires `docker compose` or `docker-compose`)

1.  Create a `docker-compose.yml` file (example below, adjust as needed).
2.  Build the images:
    ```bash
    docker compose build
    ```
3.  Run the services:
    ```bash
    # Run database migration first if needed (can be tricky with compose)
    # docker compose run --rm backend alembic upgrade head

    docker compose up -d
    ```

*(Note: A `docker-compose.yml` example is not provided here but would define services for the backend, frontend, and potentially the database, linking them together and managing environment variables.)*

## 6. Future Work / Improvements

*   Implement user authentication (e.g., JWT).
*   Develop a proper patient registration flow.
*   Implement actual reminder delivery (email/SMS).
*   Enhance appointment scheduling (check availability, provider selection).
*   Improve UI/UX (loading states, error handling, component design).
*   Add comprehensive unit and integration tests.
*   Set up CI/CD pipeline for automated testing and deployment. 