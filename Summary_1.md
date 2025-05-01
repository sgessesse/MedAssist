# MedAssist Project Summary (2025-04-27)

## 1. Purpose of the Application

MedAssist aims to be a virtual medical assistant chatbot designed to:
*   Provide informative answers to general medical questions using a curated knowledge base.
*   Perform preliminary symptom triage based on predefined rules to suggest appropriate levels of care (e.g., Self-Care, Doctor Soon, Emergency Room).
*   Assist users (patients) with scheduling appointments.
*   Help users set reminders for medications, appointments, or other health-related tasks.
*   **Disclaimer:** The application simulates assistant functionalities and is NOT intended as a substitute for professional medical advice, diagnosis, or treatment.

## 2. Functionality Overview

*   **Conversational Interface:** Users interact with the assistant via a chat UI.
*   **Medical Q&A:** Leverages Retrieval-Augmented Generation (RAG) to answer questions based on information ingested into a vector database (from sources like MedlinePlus, openFDA).
*   **Symptom Triage:** Analyzes user-described symptoms against a ruleset (`symptom_rules.json`) to provide a basic triage recommendation.
*   **Appointment Scheduling:** Allows users to request appointments via chat, which are then created in a backend database.
*   **Reminder Setting:** Allows users to request reminders via chat, which are stored in the backend database.
*   **Contextual Memory:** The chatbot maintains conversation history within a session to understand follow-up questions.

## 3. Architectural Design

*   **Monorepo Structure:** Backend and frontend code reside in the same repository (`backend/`, `frontend/`).
*   **Backend:**
    *   **Framework:** FastAPI (Python) for creating the REST API.
    *   **Language Model:** Google Gemini (specifically `gemini-1.5-flash-latest` currently).
    *   **Orchestration:** LangChain framework for managing the LLM, prompt templates, tools, memory, and agent execution.
    *   **Database:** PostgreSQL.
    *   **ORM:** SQLAlchemy for database interaction.
    *   **Vector Store:** ChromaDB for storing and retrieving embeddings of the medical knowledge base.
    *   **Key Modules:**
        *   `main.py`: FastAPI app setup, middleware (CORS), router inclusion.
        *   `database.py`: SQLAlchemy engine, session management (`SessionLocal`, `get_db` dependency).
        *   `models.py`: SQLAlchemy ORM models (`Patient`, `Appointment`, `Reminder`).
        *   `schemas.py`: Pydantic models for API request/response validation and serialization.
        *   `crud.py`: Database Create, Read, Update, Delete operations for models.
        *   `core/config.py`: Centralized configuration loading from `.env` using `pydantic-settings`.
        *   `agent.py`: Core agent logic - LLM initialization, tool definitions (`@tool`), prompt template, memory setup (`ConversationBufferMemory`, `RunnableWithMessageHistory`), agent creation (`create_tool_calling_agent`, `AgentExecutor`), response processing (including source extraction).
        *   `api/endpoints/`: FastAPI routers (`chat.py`, `schedule.py`, `reminder.py`) defining specific API paths and linking them to agent/CRUD functions.
*   **Frontend:**
    *   **Framework:** Next.js (React framework) with App Router.
    *   **Language:** TypeScript.
    *   **Styling:** Tailwind CSS.
    *   **Key Components:**
        *   `ChatInterface.tsx`: Main UI component managing chat state, message display (including sources), input handling, and API calls to the backend `/chat` endpoint.
        *   `app/page.tsx`: Renders the `ChatInterface`.

## 4. What We Have Done So Far

*   **Backend Setup:** Initialized FastAPI, configured CORS, set up database connection and SQLAlchemy models/schemas.
*   **Configuration:** Implemented centralized settings loading from `.env`.
*   **Knowledge Base Ingestion:** (Assumed done via `scripts/ingest_vector_db.py`) Created ChromaDB vector store.
*   **Agent Implementation:**
    *   Initialized Gemini LLM and embeddings.
    *   Defined LangChain tools for `search_medical_knowledge`, `triage_symptoms`, `schedule_appointment`, `set_reminder`.
    *   Implemented basic rule-based triage logic.
    *   Set up agent prompt providing persona and instructions.
    *   Integrated conversational memory.
    *   Created the main agent executor.
*   **CRUD Implementation:** Wrote functions in `crud.py` for database operations on patients, appointments, and reminders.
*   **API Endpoints:** Implemented FastAPI endpoints for chat, scheduling (create, get by patient/ID, delete), and reminders (create, get by patient/ID, delete).
*   **Integration:**
    *   Connected chat endpoint (`/api/v1/chat`) to the LangChain agent (`get_agent_response`).
    *   Connected scheduling/reminder tools and API endpoints to the corresponding CRUD functions.
    *   Implemented patient ID lookup (mapping chat `user_id` to `patient_db_id`) and passed context to the agent.
    *   Refined time parsing in tools using `dateparser` with relative base.
    *   Implemented structured source extraction (parsing `[Source:...]` from the agent's final reply).
*   **Frontend Setup:** Initialized Next.js app, created basic `ChatInterface` component.
*   **Frontend-Backend Connection:** Successfully connected the frontend chat UI to the backend API, sending messages and displaying responses (including sources).
*   **Debugging:** Resolved numerous issues related to environment variables, LangChain memory/history, agent tool usage, Python syntax errors, patient ID context passing, and time parsing.

## 5. Remaining Tasks / Future Work

*   **Frontend:**
    *   Implement user authentication UI (login/signup).
    *   Replace hardcoded `user_id` with authenticated user's ID.
    *   Improve UI/UX (e.g., better loading/error states, styling).
    *   Potentially display `triage_tag` visually if implemented.
    *   Consider adding UI for viewing/managing appointments/reminders.
*   **Backend / Agent:**
    *   **Triage Tag:** Implement reliable extraction of the triage tag into the `ChatResponse` (potentially by modifying tool output format or prompt).
    *   **Background Tasks:** Implement actual reminder delivery mechanism (e.g., email simulation, Celery/APScheduler for real tasks).
    *   **Authentication:** Implement secure backend authentication (e.g., JWT) to protect endpoints and associate requests with users.
    *   **Time Parsing:** Further investigate/refine handling of complex relative dates if needed.
    *   **Error Handling:** Enhance error handling and logging throughout the backend.
    *   **Logging:** Fix issue preventing agent execution step logs (`verbose=True`) from appearing correctly.
    *   **Testing:** Add unit and integration tests for API endpoints, CRUD functions, and agent logic.
    *   **Provider Logic:** Implement dynamic provider assignment/selection for appointments.
    *   **Slot Availability:** Add logic to check for actual appointment slot availability.
*   **Deployment:**
    *   Containerize backend and frontend (Dockerfiles).
    *   Set up database migrations (e.g., using Alembic).
    *   Configure production database.
    *   Deploy backend (e.g., Render, Fly.io, AWS).
    *   Deploy frontend (e.g., Vercel, Netlify).
*   **Data & Rules:**
    *   Expand/update the medical knowledge base.
    *   Refine and expand the symptom triage ruleset. 